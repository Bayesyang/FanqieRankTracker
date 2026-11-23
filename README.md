# 🏆 番茄风向标 · Fanqie Rank Tracker

[![English](https://img.shields.io/badge/lang-English-blue)](README_EN.md)

> 每日自动追踪**番茄小说男女频新书榜**，分频道存储历史数据、生成 AI 趋势分析并部署为在线看板。首页、趋势页和作品详情页支持频道切换。

---

## ✨ 功能概览

| 功能 | 说明 |
|------|------|
| 🕷️ 自动爬取 | 每日定时抓取男女频各分类的新书榜，每类最多 30 本（实际以页面加载数量为准） |
| 🔀 男女频切换 | 男女频独立采集、存储、对比和分析；保留原女频历史路径与接口兼容 |
| 📊 趋势对比 | 自动对比相邻两天数据：新上榜 / 掉榜 / 排名变化 / 阅读量增长 |
| 🤖 AI 风向分析 | 接入 OpenAI 兼容 API，按分类生成市场趋势速评 |
| 🧭 类型风向标 | 独立趋势页聚合多日数据，用 AI 总结古风言情等综合赛道、具体热门分类和高频题材；未配置 API 时自动规则兜底 |
| 📚 短篇推荐 | 访问时按 99 个题材标签实时读取短故事，展示封面、摘要、阅读时长和互动数据，不落盘推荐内容 |
| 🖥️ 精美看板 | 暗色编辑风格仪表盘，带打字机动画和瀑布流书籍卡片 |
| 📱 移动适配 | 完整的移动端适配，侧边栏抽屉式菜单 |
| 🔌 数据接口 | 生成静态 `lastest` JSON 接口，可按类型读取最新数据 |
| ⚡ 全自动化 | GitHub Actions + GitHub Pages，零服务器运维 |

---

## 🚀 食用指南

### 前置条件

- **Python 3.9+**
- **Git**
- 一个 GitHub 账号
- （可选）一个 OpenAI 兼容 API 的密钥，用于 AI 分析

### 第一步：Fork 仓库

点击 GitHub 页面右上角的 **Fork** 按钮，将项目 Fork 到你自己的账号下。

### 第二步：开启 GitHub Pages

1. 进入你 Fork 后的仓库 → **Settings** → **Pages**
2. Source 选择 **GitHub Actions**（仓库工作流使用 artifact 部署，不要选择分支部署）
3. 进入 **Actions**，允许 Fork 仓库运行工作流；保留 `main` 分支

稍等几分钟，你的看板就会上线：`https://<你的用户名>.github.io/FanqieRankTracker/`

### 第三步：配置 Secrets（可选，开启 AI 分析）

进入仓库 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**，添加以下三个 Secret：

| Secret 名称 | 说明 | 示例 |
|---|---|---|
| `API_BASE_URL` | OpenAI 兼容 API 的地址 | `https://api.openai.com/v1` |
| `API_KEY` | API 密钥 | `sk-xxxxxxxxxxxxx` |
| `API_MODEL` | 模型名称 | `gpt-4o-mini` |

> **💡 提示：** 任何 OpenAI 兼容接口均可使用（如 Moonshot / DeepSeek / 自建服务等）。如果不配置这三个 Secret，系统将自动使用基于规则的摘要替代 AI 分析，**不影响核心功能**。

### 第四步：手动触发首次运行

1. 进入仓库 → **Actions** → 左侧选择 **Daily Fanqie Rank Scraper**
2. 点击右上角 **Run workflow**，选择 `channel=all`（男女频）或单独的 `male` / `female`
3. 等待 Workflow 运行完成，耗时随分类数量、网站响应和 AI 服务而变化

运行成功后，`data/` 目录下会自动生成数据文件，打开 GitHub Pages 链接即可看到看板。

### 第五步：坐等自动更新

GitHub Actions 已配置为 **每天 UTC 00:00（北京时间 08:00）** 自动采集男女频（实际启动可能延迟）。同一天重复运行按已完成分类续传，空数据不会标记成功；强制更新工作流可选择频道并重新采集当天数据。

首页通过 `?channel=male` / `?channel=female` 选择频道，未指定时默认女频。初次改造后男频尚无快照时会显示待采集提示，不会拿女频数据填充。每个频道至少两份快照后才能生成趋势对比。

看板右上角的 **风向标** 可进入 `trend.html`，先查看当下火热综合赛道（如古风言情）、具体热门分类和高频题材，再按具体类型查看近 7 / 14 / 30 日或全部周期的趋势分析。全站热点会优先使用 AI 总结，未配置 API 或生成失败时使用规则统计文案兜底。

---

## 🔌 最新数据接口

构建脚本会同步生成 GitHub Pages 可直接访问的静态 JSON 接口：

| 类型 | 路径 | 说明 |
|---|---|---|
| 类型索引 | `api/lastest.json` | 返回所有可用类型及对应 URL |
| 全量数据 | `api/lastest/all.json` | `type=all`，返回全部分类、趋势和书籍 |
| 单类型数据 | `api/lastest/<类型>.json` | 返回指定类型的数据，例如 `api/lastest/古风世情.json` |
| 男频类型索引 | `api/male/lastest.json` | 男频可用类型与对应 URL |
| 男频全量数据 | `api/male/lastest/all.json` | 仅男频分类、趋势和书籍 |
| 男频单类型数据 | `api/male/lastest/<类型>.json` | 例如 `api/male/lastest/东方仙侠.json` |

原有 `data/`、`api/lastest*` 继续代表女频；男频快照、进度、趋势和日期索引独立保存在 `data/male/`，接口在 `api/male/`。两频道的分类路由、赛道分组和题材词统一配置于 `channels.json`，Python 与前端共用，切勿将女频快照复制到男频目录。

示例：

```bash
curl https://<你的用户名>.github.io/FanqieRankTracker/api/lastest/all.json
curl https://<你的用户名>.github.io/FanqieRankTracker/api/lastest/古风世情.json
```

---

## 🔧 本地开发

```bash
# 1. 克隆仓库
git clone https://github.com/<你的用户名>/FanqieRankTracker.git
cd FanqieRankTracker

# 2. 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt
playwright install chromium

# 4. 运行爬虫（默认男女频，--channel male / female 可单独运行）
python scrape_fanqie_ranks.py --channel all

# 5. 构建看板数据（可选，带 AI 分析需设置环境变量）
pip install openai
export API_BASE_URL="https://your-api-endpoint/v1"
export API_KEY="your-api-key"
export API_MODEL="your-model-name"
python scripts/build_latest.py --channel all

# 6. 本地预览前端
python -m http.server 8000
# 打开 http://localhost:8000
# 男频：http://localhost:8000/?channel=male
```

本地和 Actions 均使用 Playwright Chromium，无需另装 Google Chrome。`--force` 在爬虫中表示忽略当天进度重新采集，在构建脚本中表示重新生成 AI 摘要。历史日期只能重新构建已有快照，不能补抓过去的榜单。

短篇推荐是独立功能，`shorts.html` 当前连接外部 Cloudflare Worker；仓库未附 Worker 源码，自部署榜单不依赖它，短篇接口可用性由外部服务决定。

### 回归测试

```bash
python -m unittest discover -s tests -v
node --test tests/test_channels.js
python tests/browser_smoke.py
```

浏览器测试使用临时男频样本，不会修改真实快照或调用 AI 服务；默认使用 Playwright Chromium，也可设置 `BROWSER_CHANNEL=chrome` 使用系统 Chrome。

---

## 📁 项目结构

```
FanqieRankTracker/
├── .github/workflows/
│   └── scrape.yml              # GitHub Actions 自动化工作流
├── css/
│   └── style.css               # 暗色编辑风格主题样式
├── js/
│   └── app.js                  # 前端渲染逻辑（瀑布流 + 打字机动画）
├── scripts/
│   └── build_latest.py         # 趋势对比 + AI 分析构建脚本
├── channels.json               # 男女频路由、路径、赛道分组与题材词
├── rank_config.py              # Python 频道配置读取与分类校验
├── data/
│   ├── male/                   # 男频独立快照、趋势、日期与最新数据
│   ├── fanqie_female_new_ranks_YYYYMMDD.json  # 每日原始快照
│   ├── latest_ranks.json       # 最新聚合数据（看板数据源）
│   ├── market_summary.json     # 全站热点 AI/规则总结
│   └── trends/
│       └── YYYY-MM-DD.json     # 趋势归档
├── api/
│   ├── male/                   # 男频静态接口
│   └── lastest/                # 最新数据静态接口（all + 按类型拆分）
├── index.html                  # 仪表盘入口页
├── trend.html                  # 类型风向标趋势分析页
├── shorts.html                 # 短篇推荐页
├── scrape_fanqie_ranks.py      # 番茄小说爬虫（Playwright）
├── requirements.txt            # Python 依赖
└── README.md                   # 本文件
```

---

## ⚙️ 工作流程

```
┌─────────────────────────────────────────────────────────────┐
│                   GitHub Actions (每日 08:00)                │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  Playwright   │───▶│  build_latest │───▶│  git commit  │  │
│  │  爬取榜单数据  │    │  趋势对比      │    │  自动提交     │  │
│  │              │    │  + AI 分析     │    │  到 main     │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│                                                             │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
                    GitHub Pages 自动部署
                    用户访问在线看板 🌐
```

---

## 📝 常见问题

<details>
<summary><b>Q: Workflow 运行失败怎么办？</b></summary>

检查 Actions 日志中的错误信息。常见原因：
- 番茄小说页面结构变更 → 需要更新爬虫选择器
- Playwright 安装超时 → 尝试重新运行

</details>

<details>
<summary><b>Q: 不配置 AI Secret 也能用吗？</b></summary>

可以！系统会自动 fallback 到基于规则的摘要（如"新增3本上榜；《XX》排名上升+5位"）。只是没有 AI 自然语言分析而已。

</details>

<details>
<summary><b>Q: 可以换成男频或其他榜单吗？</b></summary>

男频已内置，使用首页频道切换或 `--channel male` 即可。新增其他榜单需同步配置入口与路由筛选、独立的数据/API 路径、快照前缀和赛道分组；不能只改入口 URL，否则会串榜。

</details>

---

## 📜 License

MIT

---

<p align="center">
  <sub>Made with ☕ and 🤖 — 数据每日自动更新，无需手动维护</sub>
</p>
