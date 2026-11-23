"""男女频共用配置；女频保留原有路径以兼容历史数据和接口。"""
import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
with (BASE_DIR / "channels.json").open(encoding="utf-8") as config_file:
    CHANNELS = json.load(config_file)


def get_channel(channel="female"):
    if channel not in CHANNELS:
        raise ValueError(f"未知频道: {channel}")
    return CHANNELS[channel]


def selected_channels(channel):
    if channel == "all":
        return list(CHANNELS)
    get_channel(channel)
    return [channel]


def channel_categories(links, channel):
    """限定频道/榜单，并按链接去重（页面可能含桌面和移动两套导航）。"""
    prefix = get_channel(channel)["rank_prefix"]
    seen = set()
    result = []
    for link in links:
        href = link.get("href") or ""
        name = (link.get("name") or "").strip()
        if not name or not href.startswith(prefix) or href in seen:
            continue
        seen.add(href)
        result.append({"name": name, "href": href})
    return result
