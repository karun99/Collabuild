"""Enhanced web data fetcher for research.

Fetches URLs, extracts clean text content, handles:
  • HTML → clean text extraction (stdlib html.parser)
  • PDF detection and handling
  • Redirect following
  • Rate limiting and retries
  • Content summarization (truncation with structure preservation)

No external dependencies — stdlib only.
"""

import contextlib
import html.parser
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict

log = logging.getLogger("research.fetcher")


class _HTMLTextExtractor(html.parser.HTMLParser):
    """Extract readable text from HTML, skipping scripts/styles/nav."""

    SKIP_TAGS = {"script", "style", "nav", "header", "footer", "aside", "noscript", "iframe"}
    BLOCK_TAGS = {"p", "div", "br", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "blockquote", "pre", "section", "article"}

    def __init__(self):
        super().__init__()
        self._parts = []
        self._skip_depth = 0
        self._tag_stack = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        self._tag_stack.append(tag)
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
        if self._skip_depth == 0 and tag in self.BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()
        if tag in self.SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        if self._skip_depth == 0 and tag in self.BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data):
        if self._skip_depth == 0:
            self._parts.append(data)

    def get_text(self) -> str:
        raw = "".join(self._parts)
        lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in raw.split('\n')]
        return "\n".join(line for line in lines if line)


class _HTMLMetaExtractor(html.parser.HTMLParser):
    """Extract title and meta description from HTML head."""

    def __init__(self):
        super().__init__()
        self.title = ""
        self.description = ""
        self.in_title = False
        self.in_head = False
        self.depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "head":
            self.in_head = True
        if tag == "title" and self.in_head:
            self.in_title = True
        if tag == "meta":
            attrs_dict = dict(attrs)
            name = attrs_dict.get("name", "").lower()
            if name == "description":
                self.description = attrs_dict.get("content", "")

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self.in_title = False
        if tag.lower() == "head":
            self.in_head = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data


class WebFetcher:
    """Enhanced web fetcher for research data collection.

    Args:
        user_agent: custom User-Agent string
        timeout: request timeout in seconds
        max_retries: retry count on failure
        retry_delay: seconds between retries
        max_content_length: max response size in bytes (default 10MB)
    """

    DEFAULT_UA = ("Mozilla/5.0 (compatible; CollabuildResearch/1.0; "
                  "+https://github.com/collabuild-mas)")

    def __init__(self, user_agent: str = "", timeout: int = 30,
                 max_retries: int = 3, retry_delay: float = 2.0,
                 max_content_length: int = 10 * 1024 * 1024):
        self.user_agent = user_agent or self.DEFAULT_UA
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.max_content_length = max_content_length
        self._cache = OrderedDict()
        self._cache_max = 100

    def _make_request(self, url: str, follow_redirects: bool = True) -> tuple:
        """Make HTTP request with retries. Returns (status, headers, body_bytes)."""
        opener = urllib.request.build_opener()
        if not follow_redirects:
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, req, fp, code, msg, headers, newurl):
                    raise urllib.error.HTTPError(newurl, code, msg, headers, fp)
            opener = urllib.request.build_opener(NoRedirect)

        req = urllib.request.Request(url, headers={
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })

        last_err = None
        for attempt in range(self.max_retries):
            try:
                resp = opener.open(req, timeout=self.timeout)
                body = resp.read(self.max_content_length + 1)
                too_large = len(body) > self.max_content_length
                return resp.status, dict(resp.headers), body[:self.max_content_length], too_large
            except urllib.error.HTTPError as e:
                last_err = e
                if e.code in (404, 410):
                    return e.code, {}, b"", False
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
            except (urllib.error.URLError, OSError) as e:
                last_err = e
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))

        raise ConnectionError(f"Failed to fetch {url} after {self.max_retries} retries: {last_err}")

    def fetch_url(self, url: str) -> dict:
        """Fetch a URL and extract structured content.

        Returns:
            {
                "url": final_url,
                "status": int,
                "content_type": str,
                "title": str,
                "description": str,
                "text": str (clean extracted text),
                "is_pdf": bool,
                "truncated": bool,
                "word_count": int,
            }
        """
        if url in self._cache:
            log.debug("[fetcher] cache hit: %s", url)
            return self._cache[url]

        log.info("[fetcher] fetching: %s", url)
        status, headers, body, truncated = self._make_request(url)
        content_type = headers.get("Content-Type", headers.get("content-type", ""))

        result = {
            "url": url,
            "status": status,
            "content_type": content_type,
            "title": "",
            "description": "",
            "text": "",
            "is_pdf": False,
            "truncated": truncated,
            "word_count": 0,
        }

        if status >= 400:
            result["text"] = f"[HTTP {status}]"
            return result

        # PDF detection
        if "pdf" in content_type or url.lower().endswith(".pdf"):
            result["is_pdf"] = True
            result["text"] = f"[PDF document detected: {len(body)} bytes] Use Baidu OCR to extract text."
            result["word_count"] = 0
            self._cache_put(url, result)
            return result

        # HTML text extraction
        try:
            html_text = body.decode("utf-8", errors="replace")
        except Exception:
            html_text = body.decode("latin-1", errors="replace")

        meta = _HTMLMetaExtractor()
        with contextlib.suppress(Exception):
            meta.feed(html_text)
        result["title"] = meta.title.strip()
        result["description"] = meta.description.strip()

        extractor = _HTMLTextExtractor()
        with contextlib.suppress(Exception):
            extractor.feed(html_text)
        result["text"] = extractor.get_text()
        result["word_count"] = len(result["text"].split())

        self._cache_put(url, result)
        return result

    def fetch_multiple(self, urls: list, delay: float = 1.0) -> list:
        """Fetch multiple URLs with rate limiting. Returns list of result dicts."""
        results = []
        for i, url in enumerate(urls):
            try:
                r = self.fetch_url(url)
                results.append(r)
            except Exception as e:
                log.error("[fetcher] failed: %s — %s", url, e)
                results.append({"url": url, "status": 0, "text": f"[FETCH FAILED: {e}]", "error": str(e)})
            if delay > 0 and i < len(urls) - 1:
                time.sleep(delay)
        return results

    def search_and_extract(self, query: str, urls: list = None) -> dict:
        """High-level research fetch: extract content from URLs relevant to a query.

        If no URLs provided, returns empty results. This is meant to be called
        with URLs discovered by a search step.
        """
        if not urls:
            return {"query": query, "results": [], "total_words": 0}

        results = self.fetch_multiple(urls)
        total_words = sum(r.get("word_count", 0) for r in results)
        return {
            "query": query,
            "results": results,
            "total_words": total_words,
        }

    def extract_text(self, html: str) -> str:
        """Extract clean text from raw HTML string."""
        extractor = _HTMLTextExtractor()
        with contextlib.suppress(Exception):
            extractor.feed(html)
        return extractor.get_text()

    def summarize(self, text: str, max_words: int = 500) -> str:
        """Simple extractive summarization — first N words with structure."""
        words = text.split()
        if len(words) <= max_words:
            return text
        truncated = " ".join(words[:max_words])
        return truncated + f"\n\n[... truncated, {len(words)} total words]"

    def _cache_put(self, url: str, result: dict):
        if len(self._cache) >= self._cache_max:
            self._cache.popitem(last=False)
        self._cache[url] = result

    def status(self) -> dict:
        return {
            "provider": "web_fetcher",
            "cache_size": len(self._cache),
            "max_cache": self._cache_max,
            "timeout": self.timeout,
            "retries": self.max_retries,
            "max_content_mb": self.max_content_length / (1024 * 1024),
        }
