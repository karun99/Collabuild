"""Channel-based internet access for AI agents.

Each channel wraps an upstream tool (yt-dlp, gh CLI, bili-cli, etc.)
and provides a consistent check() interface. Channels are tiered:

  Tier 0: Zero-config (web, YouTube, GitHub, RSS, search, V2EX)
  Tier 1: Free login (Twitter, Bilibili)
  Tier 2: Manual setup (Reddit, Facebook, Instagram)
"""

import logging
import os
import shutil
import subprocess
from abc import ABC, abstractmethod

log = logging.getLogger("collabuild.reach")


class CheckResult:
    """Result of a channel health check."""

    def __init__(self, status: str, message: str):
        self.status = status  # 'ok' | 'warn' | 'error' | 'off'
        self.message = message

    def __repr__(self) -> str:
        return f"<CheckResult {self.status}: {self.message}>"


class Channel(ABC):
    """Base class for an internet access channel."""

    name: str = ""
    description: str = ""
    backends: list[str] = []
    tier: int = 0
    active_backend: str | None = None

    @abstractmethod
    def check(self, config: dict | None = None) -> CheckResult:
        ...

    def can_handle(self, url: str) -> bool:
        return False

    def read(self, url: str) -> str:
        raise NotImplementedError(f"{self.name} does not support read()")


class WebChannel(Channel):
    """Read any web page via Jina Reader (free, no auth)."""

    name = "web"
    description = "任意网页"
    backends = ["Jina Reader"]
    tier = 0

    def check(self, config: dict | None = None) -> CheckResult:
        self.active_backend = "Jina Reader"
        return CheckResult("ok", "通过 Jina Reader 读取任意网页（curl https://r.jina.ai/URL）")

    def can_handle(self, url: str) -> bool:
        return url.startswith(("http://", "https://"))

    def read(self, url: str) -> str:
        import urllib.request

        jina_url = f"https://r.jina.ai/{url}"
        req = urllib.request.Request(
            jina_url,
            headers={"User-Agent": "CollabuildReach/1.0", "Accept": "text/plain"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8")


class YouTubeChannel(Channel):
    """YouTube subtitles and search via yt-dlp."""

    name = "youtube"
    description = "YouTube 字幕提取 + 搜索"
    backends = ["yt-dlp"]
    tier = 0

    def check(self, config: dict | None = None) -> CheckResult:
        if shutil.which("yt-dlp"):
            try:
                subprocess.run(["yt-dlp", "--version"], capture_output=True, timeout=10)
                self.active_backend = "yt-dlp"
                return CheckResult("ok", "yt-dlp 已安装，可用于字幕提取和搜索")
            except Exception:
                return CheckResult("warn", "yt-dlp 存在但无法执行")
        return CheckResult("warn", "yt-dlp 未安装。安装：pip install yt-dlp")

    def can_handle(self, url: str) -> bool:
        return "youtube.com" in url or "youtu.be" in url


class GitHubChannel(Channel):
    """GitHub repository access via gh CLI."""

    name = "github"
    description = "GitHub 仓库和搜索"
    backends = ["gh CLI"]
    tier = 0

    def check(self, config: dict | None = None) -> CheckResult:
        if shutil.which("gh"):
            try:
                subprocess.run(["gh", "--version"], capture_output=True, timeout=10)
                self.active_backend = "gh CLI"
                has_auth = bool(os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"))
                if has_auth:
                    return CheckResult("ok", "gh CLI 已安装，已配置认证")
                return CheckResult("ok", "gh CLI 已安装（运行 gh auth login 解锁私有仓库）")
            except Exception:
                return CheckResult("error", "gh 命令存在但无法执行")
        return CheckResult("warn", "gh CLI 未安装。安装：https://cli.github.com")

    def can_handle(self, url: str) -> bool:
        return "github.com" in url


class ExaSearchChannel(Channel):
    """Semantic web search via Exa (MCP, free, no API key)."""

    name = "search"
    description = "全网语义搜索"
    backends = ["mcporter (Exa)"]
    tier = 0

    def check(self, config: dict | None = None) -> CheckResult:
        if shutil.which("mcporter"):
            self.active_backend = "mcporter (Exa)"
            return CheckResult("ok", "Exa 语义搜索可用（免费，无需 API Key）")
        if shutil.which("npx"):
            try:
                subprocess.run(
                    ["npx", "mcporter@latest", "--version"],
                    capture_output=True,
                    timeout=8,
                )
                self.active_backend = "mcporter (Exa)"
                return CheckResult("ok", "Exa 语义搜索可用（免费，无需 API Key）")
            except Exception:
                pass
        return CheckResult("warn", "mcporter 未安装。安装：npm install -g mcporter")


class RSSChannel(Channel):
    """RSS/Atom feed reader via feedparser."""

    name = "rss"
    description = "RSS/Atom 源阅读"
    backends = ["feedparser"]
    tier = 0

    def check(self, config: dict | None = None) -> CheckResult:
        try:
            import feedparser  # noqa: F401

            self.active_backend = "feedparser"
            return CheckResult("ok", "feedparser 可用，可阅读任意 RSS/Atom 源")
        except ImportError:
            return CheckResult("warn", "feedparser 未安装。安装：pip install feedparser")


class BilibiliChannel(Channel):
    """Bilibili search and video details via bili-cli."""

    name = "bilibili"
    description = "B站搜索和视频详情"
    backends = ["bili-cli"]
    tier = 1

    def check(self, config: dict | None = None) -> CheckResult:
        if shutil.which("bili"):
            try:
                subprocess.run(["bili", "--version"], capture_output=True, timeout=10)
                self.active_backend = "bili-cli"
                return CheckResult("ok", "bili-cli 已安装，无需登录即可搜索")
            except Exception:
                return CheckResult("error", "bili 存在但无法执行")
        return CheckResult("off", "bili-cli 未安装。安装：pip install bilibili-cli")


class TwitterChannel(Channel):
    """Twitter/X search via twitter-cli (needs cookies)."""

    name = "twitter"
    description = "Twitter/X 搜索和推文"
    backends = ["twitter-cli"]
    tier = 1

    def check(self, config: dict | None = None) -> CheckResult:
        if shutil.which("twitter"):
            try:
                subprocess.run(["twitter", "--version"], capture_output=True, timeout=10)
                self.active_backend = "twitter-cli"
                auth_token = os.environ.get("TWITTER_AUTH_TOKEN")
                ct0 = os.environ.get("TWITTER_CT0")
                if auth_token and ct0:
                    return CheckResult("ok", "twitter-cli 已安装，Cookie 已配置")
                return CheckResult(
                    "warn",
                    "twitter-cli 已安装，需配置 Cookie：export TWITTER_AUTH_TOKEN=... TWITTER_CT0=...",
                )
            except Exception:
                return CheckResult("error", "twitter 存在但无法执行")
        return CheckResult("off", "twitter-cli 未安装。安装：pip install twitter-cli")

    def can_handle(self, url: str) -> bool:
        return "twitter.com" in url or "x.com" in url


class RedditChannel(Channel):
    """Reddit search and posts via rdt-cli (needs login)."""

    name = "reddit"
    description = "Reddit 搜索和帖子"
    backends = ["rdt-cli"]
    tier = 2

    def check(self, config: dict | None = None) -> CheckResult:
        if shutil.which("rdt"):
            try:
                subprocess.run(["rdt", "--version"], capture_output=True, timeout=10)
                self.active_backend = "rdt-cli"
                return CheckResult("ok", "rdt-cli 已安装（需登录：rdt login）")
            except Exception:
                return CheckResult("error", "rdt 存在但无法执行")
        return CheckResult("off", "rdt-cli 未安装。安装：pip install rdt-cli")


class V2EXChannel(Channel):
    """V2EX hot topics, nodes, and posts via public API."""

    name = "v2ex"
    description = "V2EX 热门帖子、节点"
    backends = ["API"]
    tier = 0

    def check(self, config: dict | None = None) -> CheckResult:
        self.active_backend = "API"
        return CheckResult("ok", "V2EX API 可用（无需任何配置）")


_ALL_CHANNELS: list[Channel] = [
    WebChannel(),
    YouTubeChannel(),
    GitHubChannel(),
    ExaSearchChannel(),
    RSSChannel(),
    BilibiliChannel(),
    V2EXChannel(),
    TwitterChannel(),
    RedditChannel(),
]


def get_channels() -> list[Channel]:
    """Get all registered channels."""
    return list(_ALL_CHANNELS)


def get_channel(name: str) -> Channel | None:
    """Get a channel by name."""
    for ch in _ALL_CHANNELS:
        if ch.name == name:
            return ch
    return None
