import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rank_config import channel_categories, get_channel, selected_channels
from scripts.build_latest import (
    build_ai_prompt, build_batch_ai_prompt, build_channel,
    build_market_ai_prompt, build_market_summary_payload,
    collect_market_hot_genres, collect_market_hot_themes,
)


def write_snapshot(root, channel, date, reads="1万", complete=True):
    config = get_channel(channel)
    path = Path(root) / config["data_dir"] / f"{config['snapshot_prefix']}{date.replace('-', '')}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "date": date, "channel": channel, "complete": complete,
        "categories": [{"name": "科幻末世", "books": [{
            "title": f"{channel}系统末世", "url": f"https://fanqienovel.com/page/{1 if channel == 'male' else 2}",
            "reads": reads, "intro": "系统与机甲", "author": "作者",
        }]}]}, ensure_ascii=False), encoding="utf-8")
    return path


class ChannelConfigTests(unittest.TestCase):
    def test_category_routes_are_isolated_and_deduplicated(self):
        links = [
            {"name": "科幻末世", "href": "/rank/0_1_8"},
            {"name": "科幻末世", "href": "/rank/1_1_8"},
            {"name": "科幻末世", "href": "/rank/1_1_8"},
            {"name": "阅读榜", "href": "/rank/1_2_8"},
            {"name": "", "href": "/rank/1_1_9"},
            {"name": "无链接", "href": None},
        ]
        self.assertEqual(channel_categories(links, "male"), [links[1]])
        self.assertEqual(channel_categories(links, "female"), [links[0]])

    def test_unknown_channel_rejected(self):
        with self.assertRaises(ValueError):
            get_channel("../female")
        self.assertEqual(selected_channels("all"), ["female", "male"])

    def test_analysis_prompts_use_selected_channel(self):
        self.assertIn("男频", build_ai_prompt("东方仙侠", {"books": []}, {}, "male"))
        self.assertIn("男频", build_batch_ai_prompt([("东方仙侠", {"books": []}, {})], "male"))
        self.assertIn("男频", build_market_ai_prompt({"channel": "male", "periods": {}}))

    def test_genre_groups_and_keywords_are_channel_specific(self):
        hot = [{"name": "东方仙侠", "score": 100, "read_growth_total": 100,
                "new_count": 1, "dropped_count": 0, "read_count": 1, "active_days": 1}]
        self.assertEqual(collect_market_hot_genres(["东方仙侠"], hot, "male")[0]["name"], "玄幻仙侠")
        self.assertEqual(collect_market_hot_genres(["东方仙侠"], hot, "female"), [])
        output = {"categories": [{"name": "东方仙侠", "books": [{"title": "机甲面板", "intro": "模拟器"}]}]}
        rows = [{"trends": {"东方仙侠": {"new_books": ["机甲面板"]}}}]
        themes = collect_market_hot_themes(output, rows, ["东方仙侠"], "male")
        self.assertEqual({item["name"] for item in themes}, {"机甲", "面板", "模拟器"})


class BuildChannelsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.env = patch.dict("os.environ", {"API_BASE_URL": "", "API_KEY": "", "API_MODEL": ""})
        self.env.start()
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()

    def tearDown(self):
        self.output.__exit__(None, None, None)
        self.env.stop()
        self.temp.cleanup()

    def read(self, path):
        return json.loads((self.root / path).read_text(encoding="utf-8"))

    def test_channels_build_independently_with_legacy_female_paths(self):
        write_snapshot(self.root, "female", "2026-11-20")
        write_snapshot(self.root, "female", "2026-11-21", "2万")
        write_snapshot(self.root, "male", "2026-11-22")
        self.assertTrue(build_channel("male", base_dir=str(self.root)))
        self.assertTrue(build_channel("female", base_dir=str(self.root)))
        male = self.read("data/male/latest_ranks.json")
        female = self.read("data/latest_ranks.json")
        self.assertEqual(male["prev_date"], "")
        self.assertEqual(female["prev_date"], "2026-11-20")
        self.assertEqual(male["categories"][0]["books"][0]["title"], "male系统末世")
        self.assertEqual(female["categories"][0]["trend"]["reads_growth"][0]["growth"], "+1.0万")
        self.assertEqual(self.read("api/male/lastest/all.json")["channel"], "male")
        self.assertEqual(self.read("api/lastest/all.json")["channel"], "female")
        self.assertEqual(self.read("api/male/lastest.json")["types"][0]["url"], "api/male/lastest/all.json")
        self.assertEqual(self.read("api/lastest.json")["types"][0]["url"], "api/lastest/all.json")
        self.assertEqual(self.read("data/male/dates.json")["dates"], ["2026-11-22"])
        self.assertEqual(self.read("data/male/market_summary.json")["channel"], "male")

    def test_incomplete_snapshots_not_published_or_used_as_baseline(self):
        write_snapshot(self.root, "male", "2026-11-20", "1万")
        write_snapshot(self.root, "male", "2026-11-21", "99万", complete=False)
        write_snapshot(self.root, "male", "2026-11-22", "2万")
        build_channel("male", base_dir=str(self.root))
        latest = self.read("data/male/latest_ranks.json")
        self.assertEqual(latest["prev_date"], "2026-11-20")
        self.assertEqual(self.read("data/male/dates.json")["dates"], ["2026-11-20", "2026-11-22"])
        self.assertEqual(latest["categories"][0]["trend"]["reads_growth"][0]["growth"], "+1.0万")

    def test_missing_male_data_never_falls_back_to_female(self):
        write_snapshot(self.root, "female", "2026-11-20")
        self.assertFalse(build_channel("male", base_dir=str(self.root)))
        self.assertFalse((self.root / "api/male/lastest/all.json").exists())
        self.assertFalse((self.root / "data/male/latest_ranks.json").exists())

    def test_target_date_selects_only_requested_channel(self):
        write_snapshot(self.root, "male", "2026-11-20")
        write_snapshot(self.root, "male", "2026-11-22")
        write_snapshot(self.root, "female", "2026-11-21")
        build_channel("male", date="2026-11-20", base_dir=str(self.root))
        self.assertEqual(self.read("data/male/latest_ranks.json")["date"], "2026-11-20")
        with self.assertRaises(ValueError):
            build_channel("male", date="2026-11-21", base_dir=str(self.root))

    def test_market_summary_uses_channel_groups(self):
        trend_dir = self.root / "trends"
        trend_dir.mkdir()
        (trend_dir / "2026-11-22.json").write_text(json.dumps({
            "date": "2026-11-22", "trends": {"东方仙侠": {"reads_growth": [{"growth": "+1000"}]}}
        }), encoding="utf-8")
        output = {"date": "2026-11-22", "categories": [{"name": "东方仙侠", "books": []}]}
        payload = build_market_summary_payload(output, str(trend_dir), "male")
        self.assertEqual(payload["periods"]["7"]["hot_genres"][0]["name"], "玄幻仙侠")


if __name__ == "__main__":
    unittest.main()
