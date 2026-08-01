"""Collabuild Reach — Agent-Reach internet capability layer for AI agents.

Give your Collabuild AI agents eyes to see the entire internet.
Provides channel-based access to: Web, YouTube, GitHub, Twitter, Reddit,
Bilibili, RSS, semantic search, and more.

Usage:
    from collabuild.reach import doctor, format_report
    results = doctor()
    print(format_report(results))
"""

from .channels import (
    BilibiliChannel,
    Channel,
    ExaSearchChannel,
    GitHubChannel,
    RedditChannel,
    RSSChannel,
    TwitterChannel,
    V2EXChannel,
    WebChannel,
    YouTubeChannel,
    get_channel,
    get_channels,
)
from .doctor import check_all, format_report, report_to_json

__all__ = [
    "Channel",
    "WebChannel",
    "YouTubeChannel",
    "GitHubChannel",
    "ExaSearchChannel",
    "RSSChannel",
    "BilibiliChannel",
    "TwitterChannel",
    "RedditChannel",
    "V2EXChannel",
    "get_channels",
    "get_channel",
    "check_all",
    "format_report",
    "report_to_json",
]
