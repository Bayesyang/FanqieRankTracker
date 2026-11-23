"""显式运行浏览器回归：python tests/browser_smoke.py（需安装 Playwright 浏览器）。

可设置 BROWSER_CHANNEL=chrome 使用系统 Chrome。男频测试数据仅在临时目录中生成，
通过请求拦截提供，不写入真实历史数据，也不调用 AI/短篇服务。
"""
import contextlib
import functools
import io
import json
import os
import sys
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit
from unittest.mock import patch

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rank_config import get_channel
from scripts.build_latest import build_channel


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def assert_page_fits(page):
    overflow = page.evaluate("""() => {
        if (document.documentElement.scrollWidth <= window.innerWidth) return [];
        return Array.from(document.querySelectorAll('body *')).filter(element => {
            const rect = element.getBoundingClientRect();
            return rect.right > window.innerWidth && getComputedStyle(element).position !== 'fixed';
        }).slice(0, 12).map(element => `${element.tagName}.${element.className}`);
    }""")
    assert not overflow, f"Horizontal page overflow: {overflow}"


def run():
    with tempfile.TemporaryDirectory() as temp:
        fixture = Path(temp)
        config = get_channel("male")
        for date, reads in [("2026-11-21", "1万"), ("2026-11-22", "2万")]:
            path = fixture / config["data_dir"] / f"{config['snapshot_prefix']}{date.replace('-', '')}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({
                "date": date, "complete": True, "channel": "male",
                "categories": [{"name": "东方仙侠", "books": [{
                    "title": "男频测试作品", "author": "测试作者", "reads": reads,
                    "intro": "系统修仙", "cover": "", "url": "https://fanqienovel.com/page/123",
                }]}],
            }, ensure_ascii=False), encoding="utf-8")
        with patch.dict(os.environ, {"API_BASE_URL": "", "API_KEY": "", "API_MODEL": ""}), \
                contextlib.redirect_stdout(io.StringIO()):
            build_channel("male", base_dir=str(fixture))

        handler = functools.partial(QuietHandler, directory=str(ROOT.parent))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}/{ROOT.name}/"
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, channel=os.environ.get("BROWSER_CHANNEL") or None)
                context = browser.new_context(viewport={"width": 1280, "height": 900})
                page = context.new_page()
                errors = []
                paths = []
                use_fixture = False
                page.on("pageerror", lambda error: errors.append(str(error)))

                def route_request(route):
                    nonlocal use_fixture
                    url = urlsplit(route.request.url)
                    if url.hostname != "127.0.0.1":
                        route.abort()
                        return
                    relative = unquote(url.path).split(f"/{ROOT.name}/", 1)[-1]
                    paths.append(relative)
                    if relative.startswith(("data/male/", "api/male/")):
                        path = fixture / relative
                        if use_fixture and path.is_file():
                            route.fulfill(status=200, content_type="application/json", body=path.read_text(encoding="utf-8"))
                        else:
                            route.fulfill(status=404, body="Not generated")
                        return
                    if relative == "data/dates.json":
                        dates = json.loads((ROOT / relative).read_text())["dates"][-2:]
                        route.fulfill(status=200, content_type="application/json", body=json.dumps({"dates": dates}))
                        return
                    route.continue_()

                page.route("**/*", route_request)
                page.goto(base)
                expect(page.locator('.channel-switch a[aria-current="page"]')).to_have_text("女频")
                expect(page.locator(".book-card").first).to_be_visible()
                paths.clear()
                page.get_by_role("link", name="男频", exact=True).click()
                expect(page.locator("#books-waterfall")).to_contain_text("男频榜单尚未生成")
                assert "data/latest_ranks.json" not in paths, paths
                print("PASS: legacy female data and male empty state; no female fallback")

                use_fixture = True
                page.reload()
                expect(page.locator(".book-card")).to_have_count(1)
                expect(page.locator(".book-title")).to_have_text("男频测试作品")
                page.locator("#date-prev").click()
                expect(page.locator("#date-display")).to_have_text("2026-11-21")
                expect(page.locator(".book-reads")).to_have_text("1万")
                page.locator("#date-next").click()
                expect(page.locator(".book-reads")).to_have_text("2万")
                page.locator(".book-card").click()
                expect(page.locator(".detail-main h1")).to_have_text("男频测试作品")
                expect(page.locator(".detail-main .panel-kicker")).to_contain_text("男频")
                assert "channel=male" in page.url
                page.get_by_role("link", name="风向标", exact=True).click()
                expect(page.locator("#trend-subtitle")).to_contain_text("男频 · 东方仙侠")
                expect(page.locator("#hot-genre-list")).to_contain_text("玄幻仙侠")
                assert "channel=male" in page.url
                print("PASS: male latest/history/detail/trends and genre grouping")

                page.get_by_role("link", name="女频", exact=True).click()
                expect(page.locator("#trend-subtitle")).to_contain_text("女频")
                expect(page.locator("#trend-category-buttons")).not_to_contain_text("东方仙侠")
                print("PASS: trend channel switching clears incompatible categories")

                page.set_viewport_size({"width": 360, "height": 800})
                page.goto(f"{base}?channel=male")
                expect(page.locator(".book-card")).to_have_count(1)
                page.locator("#mobile-menu-btn").click()
                expect(page.get_by_role("link", name="男频", exact=True)).to_be_visible()
                assert_page_fits(page)
                page.goto(f"{base}book.html?id=123&channel=male")
                expect(page.locator(".detail-main h1")).to_have_text("男频测试作品")
                assert_page_fits(page)
                print("PASS: mobile layout and channel switch")
                assert not errors, errors
                browser.close()
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    run()
