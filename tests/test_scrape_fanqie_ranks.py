import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from scrape_fanqie_ranks import open_rank_page, run_scraper


class OpenRankPageTests(unittest.TestCase):
    @patch("scrape_fanqie_ranks.time.sleep")
    def test_success_waits_for_book_links_without_retry(self, sleep):
        page = Mock()

        open_rank_page(page, "https://fanqienovel.com/rank/0_1_1139")

        page.goto.assert_called_once_with(
            "https://fanqienovel.com/rank/0_1_1139",
            wait_until="domcontentloaded",
            timeout=60000,
        )
        page.wait_for_selector.assert_called_once_with(
            'a[href^="/page/"]', timeout=30000
        )
        sleep.assert_not_called()

    @patch("scrape_fanqie_ranks.time.sleep")
    def test_navigation_timeout_retries_then_succeeds(self, sleep):
        page = Mock()
        page.goto.side_effect = [PlaywrightTimeoutError("navigation timed out"), None]

        open_rank_page(page, "https://fanqienovel.com/rank/0_1_1139")

        self.assertEqual(page.goto.call_count, 2)
        page.wait_for_selector.assert_called_once()
        sleep.assert_called_once_with(5)

    @patch("scrape_fanqie_ranks.time.sleep")
    def test_missing_book_links_retries_then_succeeds(self, sleep):
        page = Mock()
        page.wait_for_selector.side_effect = [
            PlaywrightTimeoutError("book links timed out"), None
        ]

        open_rank_page(page, "https://fanqienovel.com/rank/0_1_1139")

        self.assertEqual(page.goto.call_count, 2)
        self.assertEqual(page.wait_for_selector.call_count, 2)
        sleep.assert_called_once_with(5)

    @patch("scrape_fanqie_ranks.time.sleep")
    def test_persistent_timeout_raises_after_three_attempts(self, sleep):
        page = Mock()
        error = PlaywrightTimeoutError("navigation timed out")
        page.goto.side_effect = error

        with self.assertRaises(PlaywrightTimeoutError) as raised:
            open_rank_page(page, "https://fanqienovel.com/rank/0_1_1139")

        self.assertIs(raised.exception, error)
        self.assertEqual(page.goto.call_count, 3)
        self.assertEqual(sleep.call_count, 2)
        page.wait_for_selector.assert_not_called()


class ScrapeChannelTests(unittest.TestCase):
    def run_scraper_case(self, books, fail_navigation=False, force=False, seed=False):
        with tempfile.TemporaryDirectory() as root:
            page = Mock()
            def evaluate(script):
                if "const bookMap" in script:
                    return books
                if "querySelectorAll('a')" in script:
                    return [{"name": "东方仙侠", "href": "/rank/1_1_1140"},
                            {"name": "古风世情", "href": "/rank/0_1_1139"}]
                return None
            page.evaluate.side_effect = evaluate
            if fail_navigation:
                page.goto.side_effect = [None, PlaywrightTimeoutError("failed"),
                                         PlaywrightTimeoutError("failed"), PlaywrightTimeoutError("failed")]
            playwright = MagicMock()
            playwright.__enter__.return_value.chromium.launch.return_value.new_context.return_value.new_page.return_value = page
            from datetime import datetime, timezone
            today = datetime.now(timezone.utc).strftime("%Y%m%d")
            data_dir = Path(root) / "data/male"
            if seed:
                data_dir.mkdir(parents=True)
                (data_dir / f"task_state_{today}.json").write_text(json.dumps({"completed": ["东方仙侠"]}))
                (data_dir / f"fanqie_male_new_ranks_{today}.json").write_text(json.dumps({
                    "categories": [{"name": "东方仙侠", "books": [{"title": "旧数据"}]}]
                }))
            with patch("scrape_fanqie_ranks.BASE_DIR", Path(root)), \
                    patch("scrape_fanqie_ranks.sync_playwright", return_value=playwright), \
                    patch("scrape_fanqie_ranks.time.sleep"):
                if not books or fail_navigation:
                    with self.assertRaises(RuntimeError):
                        run_scraper(channel="male", sleep_sec=0, force=force)
                else:
                    run_scraper(channel="male", sleep_sec=0, force=force)
            files = {path.name: json.loads(path.read_text()) for path in data_dir.glob("*.json")}
            self.assertFalse((Path(root) / "data/latest_ranks.json").exists())
            return files, page

    def test_empty_category_not_marked_complete(self):
        files, _ = self.run_scraper_case([])
        self.assertEqual(files, {})

    def test_navigation_failure_does_not_extract_previous_category(self):
        files, page = self.run_scraper_case([{"title": "新书"}], fail_navigation=True)
        self.assertEqual(files, {})
        self.assertEqual(page.evaluate.call_count, 1)

    def test_success_stores_only_male_categories(self):
        files, _ = self.run_scraper_case([{"title": "新书", "reads": "在读：1万", "url": "/page/123"}])
        snapshot = next(value for key, value in files.items() if key.startswith("fanqie_"))
        self.assertTrue(snapshot["complete"])
        self.assertEqual(snapshot["channel"], "male")
        self.assertEqual([cat["name"] for cat in snapshot["categories"]], ["东方仙侠"])

    def test_force_really_replaces_completed_category(self):
        files, _ = self.run_scraper_case([{"title": "新数据", "url": "/page/123"}], force=True, seed=True)
        snapshot = next(value for key, value in files.items() if key.startswith("fanqie_"))
        self.assertEqual(snapshot["categories"][0]["books"][0]["title"], "新数据")
