import os
import json
import time
import argparse
from datetime import datetime, timezone
from urllib.parse import urljoin
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright
from rank_config import BASE_DIR, CHANNELS, channel_categories, get_channel, selected_channels

START_CODE = 58344  # 0xE3E8
CHAR_SEQUENCE = [
    "D", "在", "主", "特", "家", "军", "然", "表", "场", "4", "要", "只", "v", "和", "?", "6", "别", "还", "g", "现", "儿", "岁", "?", "?", "此", "象", "月", "3", "出", "战", "工", "相", "o", "男", "直", "失", "世", "F", "都", "平", "文", "什", "V", "O", "将", "真", "T", "那", "当", "?", "会", "立", "些", "u", "是", "十", "张", "学", "气", "大", "爱", "两", "命", "全", "后", "东", "性", "通", "被", "1", "它", "乐", "接", "而", "感", "车", "山", "公", "了", "常", "以", "何", "可", "话", "先", "p", "i", "叫", "轻", "M", "士", "w", "着", "变", "尔", "快", "l", "个", "说", "少", "色", "里", "安", "花", "远", "7", "难", "师", "放", "t", "报", "认", "面", "道", "S", "?", "克", "地", "度", "I", "好", "机", "U", "民", "写", "把", "万", "同", "水", "新", "没", "书", "电", "吃", "像", "斯", "5", "为", "y", "白", "几", "日", "教", "看", "但", "第", "加", "候", "作", "上", "拉", "住", "有", "法", "r", "事", "应", "位", "利", "你", "声", "身", "国", "问", "马", "女", "他", "Y", "比", "父", "x", "A", "H", "N", "s", "X", "边", "美", "对", "所", "金", "活", "回", "意", "到", "z", "从", "j", "知", "又", "内", "因", "点", "Q", "三", "定", "8", "R", "b", "正", "或", "夫", "向", "德", "听", "更", "?", "得", "告", "并", "本", "q", "过", "记", "L", "让", "打", "f", "人", "就", "者", "去", "原", "满", "体", "做", "经", "K", "走", "如", "孩", "c", "G", "给", "使", "物", "?", "最", "笑", "部", "?", "员", "等", "受", "k", "行", "一", "条", "果", "动", "光", "门", "头", "见", "往", "自", "解", "成", "处", "天", "能", "于", "名", "其", "发", "总", "母", "的", "死", "手", "入", "路", "进", "心", "来", "h", "时", "力", "多", "开", "已", "许", "d", "至", "由", "很", "界", "n", "小", "与", "Z", "想", "代", "么", "分", "生", "口", "再", "妈", "望", "次", "西", "风", "种", "带", "J", "?", "实", "情", "才", "这", "?", "E", "我", "神", "格", "长", "觉", "间", "年", "眼", "无", "不", "亲", "关", "结", "0", "友", "信", "下", "却", "重", "己", "老", "2", "音", "字", "m", "呢", "明", "之", "前", "高", "P", "B", "目", "太", "e", "9", "起", "稜", "她", "也", "W", "用", "方", "子", "英", "每", "理", "便", "四", "数", "期", "中", "C", "外", "样", "a", "海", "们", "任"
]

def decode_text(text: str) -> str:
    if not text:
        return ""
    result = []
    for char in text:
        code = ord(char)
        idx = code - START_CODE
        if 0 <= idx < len(CHAR_SEQUENCE):
            result.append(CHAR_SEQUENCE[idx])
        else:
            result.append(char)
    return "".join(result)

# 我们将直接从页面解析所有新书榜类别目录，实现动态抓取

def open_rank_page(page, url):
    for attempt in range(3):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_selector('a[href^="/page/"]', timeout=30000)
            return
        except PlaywrightTimeoutError:
            if attempt == 2:
                raise
            print(f"榜单首页加载超时，5 秒后重试 ({attempt + 1}/3)")
            time.sleep(5)

def run_scraper(limit=30, sleep_sec=5, channel="female", force=False):
    if limit < 1:
        raise ValueError("limit 必须大于 0")
    config = get_channel(channel)
    output_dir = str(BASE_DIR / config["data_dir"])
    os.makedirs(output_dir, exist_ok=True)
    today = datetime.now(timezone.utc)
    date_str = today.strftime("%Y%m%d")
    output_file = os.path.join(output_dir, f"{config['snapshot_prefix']}{date_str}.json")
    state_file = os.path.join(output_dir, f"task_state_{date_str}.json")
    
    # ------------- 状态恢复逻辑 -------------
    completed_cats = []
    all_categories = []  # 收集所有分类数据
    if not force and os.path.exists(state_file):
        with open(state_file, "r", encoding="utf-8") as f:
            try:
                state = json.load(f)
                completed_cats = state.get("completed", [])
            except:
                pass
    # 如果有中断恢复的数据，先加载已有的 JSON
    if not force and os.path.exists(output_file):
        with open(output_file, "r", encoding="utf-8") as f:
            try:
                existing = json.load(f)
                all_categories = existing.get("categories", [])
            except:
                pass
    # 只恢复实际有书籍的类别，空数据不能视为采集成功。
    valid_names = {cat["name"] for cat in all_categories if cat.get("books")}
    completed_cats = [name for name in completed_cats if name in valid_names]
    failed_cats = []
    # ----------------------------------------
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Create a new context with a normal user agent
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        # 先访问新书榜的基准前缀页面，以此为入口模拟人工作业
        init_url = config["entry_url"]
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 正在初始化并访问基础榜单页：{init_url}")
        open_rank_page(page, init_url)
        
        # 动态解析页面左侧拥有的所有类别目录 (通过匹配对应的榜单路由规律)
        categories_js = """
        () => {
            return Array.from(document.querySelectorAll('a'))
                .map(a => ({
                    name: a.innerText.trim(),
                    href: a.getAttribute('href')
                }));
        }
        """
        categories = channel_categories(page.evaluate(categories_js), channel)
        if not categories:
            raise RuntimeError(f"{config['label']}未找到新书榜分类，拒绝保存空榜单")
        category_names = {cat["name"] for cat in categories}
        all_categories = [cat for cat in all_categories if cat["name"] in category_names]
        completed_cats = [name for name in completed_cats if name in category_names]
        category_order = {cat["name"]: i for i, cat in enumerate(categories)}
        print(f"✅ 成功提取到 {len(categories)} 个{config['label']}分类，开始逐类采集...")
        
        for cat in categories:
            cat_name = cat["name"]
            cat_href = cat["href"]
            
            if cat_name in completed_cats:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ⏭️ 跳过今日已经完成抓取的类别：{cat_name}")
                continue
                
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 切换类别 -> {cat_name}")
            try:
                # 整页导航，避免 SPA 切换失败后把上一类别的数据写入当前类别。
                open_rank_page(page, urljoin(init_url, cat_href))
            except Exception as e:
                print(f"切换分类出错或加载超时 {cat_name}: {e}")
                failed_cats.append(cat_name)
                continue
            
            # Scroll to load top ~30 books
            for _ in range(3):
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                time.sleep(1.5)
                
            # Extract cards. Based on helper.js: books usually are inside links a[href^="/page/"]
            # Let's use playwright evaluate to reliably traverse DOM the same way script did.
            extract_js = """
            () => {
                const bookMap = new Map();
                const links = document.querySelectorAll('a[href^="/page/"]');
                links.forEach(link => {
                    let container = link.parentElement;
                    let depth = 0;
                    while (container && depth < 6) {
                        if (container.querySelector('img') && container.innerText.includes('在读')) {
                            const href = link.getAttribute('href');
                            if (!bookMap.has(href)) {
                                bookMap.set(href, container);
                            }
                            break;
                        }
                        container = container.parentElement;
                        depth++;
                    }
                });
                
                const cards = Array.from(bookMap.values());
                const results = [];
                for (const item of cards) {
                    let imgNode = item.querySelector('img');
                    let cover = imgNode ? imgNode.getAttribute('src') : "";
                    
                    let title = "";
                    if (imgNode && imgNode.getAttribute('alt')) {
                        title = imgNode.getAttribute('alt').trim();
                    }
                    if (!title) {
                        let textTitleNode = item.querySelector('h4, .title, h1') || item.querySelector('a[href^="/page/"]');
                        if (textTitleNode) {
                            let text = textTitleNode.innerText.trim();
                            if (text && !/^\\d+$/.test(text)) {
                                title = text;
                            }
                        }
                    }
                    if (!title) title = "未知";
                    if (title.includes("榜单说明")) continue;
                    
                    let authorNode = item.querySelector('.author, .author-name') || item.querySelector('a[href^="/author-page/"]');
                    let author = authorNode ? authorNode.innerText.trim() : "未知";
                    
                    let reads = "未知";
                    const lines = item.innerText.split('\\n');
                    for (let line of lines) {
                        if (line.includes('在读')) {
                            reads = line;  // We'll decode in Python
                            break;
                        }
                    }
                    
                    let introNode = item.querySelector('.intro, .abstract, .desc');
                    let intro = introNode ? introNode.innerText.trim() : "暂无简介";
                    
                    results.push({
                        title: title,
                        author: author,
                        reads: reads,
                        intro: intro,
                        cover: cover,
                        url: item.querySelector('a[href^="/page/"]').getAttribute('href')
                    });
                }
                return results;
            }
            """
            
            try:
                books_data = page.evaluate(extract_js)
            except Exception as e:
                print(f"执行JS抽取失败 {cat_name}: {e}")
                books_data = []
            if not books_data:
                failed_cats.append(cat_name)
                print(f"⚠️ {cat_name} 没有有效书籍，不标记为完成，待下次重试")
                continue
            
            category_books = []
            for b in books_data[:limit]:
                # Apply decoding logic!
                t = decode_text(b.get("title", ""))
                a = decode_text(b.get("author", ""))
                r_raw = decode_text(b.get("reads", ""))
                i = decode_text(b.get("intro", "")).replace("\\n", " ")
                c = b.get("cover", "")
                
                # Cleanup "Reads" string (e.g. "已完结 在读：34.8万" -> "34.8万")
                if "在读" in r_raw:
                    parts = r_raw.split("在读")
                    if len(parts) > 1:
                        # removes colons
                        cleaned_r = parts[1].replace(":", "").replace("：", "").strip()
                    else:
                        cleaned_r = r_raw
                else:
                    cleaned_r = r_raw
                    
                category_books.append({
                    "title": t,
                    "author": a,
                    "reads": cleaned_r,
                    "intro": i,
                    "cover": c,
                    "url": urljoin(init_url, b.get("url", ""))
                })
            
            # 收集分类数据到内存，并增量写入 JSON
            all_categories = [cat for cat in all_categories if cat["name"] != cat_name]
            all_categories.append({
                "name": cat_name,
                "books": category_books
            })
            
            # 每完成一个分类就写入 JSON（防止中断丢数据）
            snapshot = {
                "date": today.strftime('%Y-%m-%d'),
                "channel": channel,
                "complete": False,
                "categories": sorted(all_categories, key=lambda cat: category_order[cat["name"]])
            }
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(snapshot, f, ensure_ascii=False, indent=2)
            
            # 更新状态记录
            completed_cats.append(cat_name)
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump({"completed": completed_cats}, f, ensure_ascii=False)
                
            print(f"成功抓取 {cat_name} 类别的前 {len(category_books)} 本书，且进度已存档。等待 {sleep_sec} 秒防拦截...")
            
            # 保护防封禁机制
            time.sleep(sleep_sec)
        
        browser.close()

    if failed_cats:
        raise RuntimeError(f"{config['label']}部分分类采集失败，可重跑续传: {', '.join(failed_cats)}")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "date": today.strftime('%Y-%m-%d'),
            "channel": channel,
            "complete": True,
            "categories": sorted(all_categories, key=lambda cat: category_order[cat["name"]]),
        }, f, ensure_ascii=False, indent=2)
        
    print(f"\n✅ 当日选定类目任务已完毕或刷新！数据源：{output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="抓取番茄男女频新书榜")
    parser.add_argument("--channel", choices=["all", *CHANNELS], default="all")
    parser.add_argument("--force", action="store_true", help="忽略当天进度，重新采集")
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()
    failures = []
    for channel in selected_channels(args.channel):
        try:
            print(f"开始执行番茄{get_channel(channel)['label']}新书榜抓取计划...")
            run_scraper(limit=args.limit, sleep_sec=5, channel=channel, force=args.force)
        except Exception as exc:
            print(f"❌ {channel}: {exc}")
            failures.append(channel)
    if failures:
        raise SystemExit(f"采集未全部完成: {', '.join(failures)}")
