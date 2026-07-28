"""Baidu OCR — Unlimited document parsing + general OCR.

Free tiers (verified 2026):
  • Unlimited-OCR (document parsing): 200 pages/personal, 1000 pages/enterprise
  • General OCR (high-precision): 1000 calls/month/personal, 2000/month/enterprise
  • Web image OCR: 1000 calls/month/personal
  • Table OCR V2: 500 calls/month/personal

API flow (async):
  1. POST /unlimited-ocr-parser/task       → returns task_id
  2. POST /unlimited-ocr-parser/task/query  → returns status + markdown_url / parse_result_url

General OCR flow (sync):
  POST /general-basic or /accurate_basic → returns words_result immediately

Auth: OAuth2 client_credentials → access_token
  GET https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id=KEY&client_secret=SECRET

All calls: stdlib + requests only (no SDK dependency).
"""

import base64
import logging
import os
import threading
import time

import requests as _req

log = logging.getLogger("ocr.baidu")

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB Baidu limit

# Baidu error code → human-readable message
BAIDU_ERRORS = {
    110: "Access token invalid or expired",
    111: "Invalid API key or secret",
    112: "Request rate limit exceeded",
    216: "File too large (max 100MB)",
    217: "Unsupported file format",
    401: "Insufficient quota",
    403: "Permission denied",
    502: "Service temporarily unavailable",
    503: "Task processing failed",
}

# MIME types for document formats (used in multipart upload)
MIME_TYPES = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".txt": "text/plain; charset=utf-8",
    ".csv": "text/csv; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".xml": "application/xml; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".htm": "text/html; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".rtf": "application/rtf",
    ".wps": "application/vnd.ms-works",
    ".ofd": "application/ofd+xml",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".bmp": "image/bmp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
}

# Text-based formats that may need encoding normalization
TEXT_FORMATS = {".txt", ".csv", ".json", ".xml", ".html", ".htm", ".md", ".rtf", ".wps"}


def _detect_encoding(data: bytes) -> str:
    """Detect encoding from BOM or assume UTF-8."""
    if data[:3] == b'\xef\xbb\xbf':
        return "utf-8-sig"
    if data[:2] in (b'\xff\xfe', b'\xfe\xff'):
        return "utf-16"
    if data[:4] in (b'\xff\xfe\x00\x00', b'\x00\x00\xfe\xff'):
        return "utf-32"
    return "utf-8"


def _normalize_to_utf8(data: bytes, ext: str) -> bytes:
    """Normalize text file content to UTF-8 bytes, stripping BOM if present."""
    if ext.lower() not in TEXT_FORMATS:
        return data
    enc = _detect_encoding(data)
    try:
        text = data.decode(enc)
    except (UnicodeDecodeError, LookupError):
        try:
            text = data.decode("utf-8", errors="replace")
        except Exception:
            return data
    # Strip BOM and re-encode as clean UTF-8
    if text and text[0] == '\ufeff':
        text = text[1:]
    return text.encode("utf-8")


class BaiduOCR:
    """Baidu OCR client — handles token, general OCR, and Unlimited-OCR document parsing.

    Config keys:
        api_key      (str): Baidu API Key
        secret_key   (str): Baidu Secret Key
        timeout      (int): request timeout in seconds (default 120)
        poll_interval(int): seconds between poll attempts for async tasks (default 5)
        max_polls    (int): max poll attempts before timeout (default 60)
    """

    TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"

    # General OCR endpoints
    GENERAL_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic"
    GENERAL_ACCURATE_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic"
    WEB_IMAGE_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/webimage"
    TABLE_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/table"

    # Unlimited-OCR (document parsing) endpoints
    UNLIMITED_SUBMIT_URL = "https://aip.baidubce.com/rest/2.0/brain/online/v2/unlimited-ocr-parser/task"
    UNLIMITED_QUERY_URL = "https://aip.baidubce.com/rest/2.0/brain/online/v2/unlimited-ocr-parser/task/query"

    def __init__(self, api_key: str = "", secret_key: str = "",
                 timeout: int = 120, poll_interval: int = 5, max_polls: int = 60):
        self.api_key = api_key or os.getenv("BAIDU_OCR_API_KEY", "")
        self.secret_key = secret_key or os.getenv("BAIDU_OCR_SECRET_KEY", "")
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.max_polls = max_polls
        self._token = ""
        self._token_expires = 0.0
        self._token_lock = threading.Lock()

    # ── Error handling ─────────────────────────────────────────

    @staticmethod
    def _check_response(resp: dict, context: str = "") -> None:
        """Check Baidu API response for errors, raise with readable message."""
        error_code = resp.get("error_code", 0)
        if error_code == 0:
            return
        error_msg = resp.get("error_msg", "unknown")
        readable = BAIDU_ERRORS.get(error_code, "")
        prefix = f"[{context}] " if context else ""
        detail = f" ({readable})" if readable else ""
        raise RuntimeError(f"{prefix}Baidu error {error_code}: {error_msg}{detail}")

    # ── Token management (thread-safe) ─────────────────────────

    def _get_token(self) -> str:
        """Get or refresh OAuth2 access_token (cached until expiry, thread-safe)."""
        with self._token_lock:
            now = time.time()
            if self._token and now < self._token_expires - 60:
                return self._token
            if not self.api_key or not self.secret_key:
                raise ValueError(
                    "Baidu OCR: api_key and secret_key required. "
                    "Set BAIDU_OCR_API_KEY / BAIDU_OCR_SECRET_KEY env vars."
                )
            r = _req.get(self.TOKEN_URL, params={
                "grant_type": "client_credentials",
                "client_id": self.api_key,
                "client_secret": self.secret_key,
            }, timeout=30)
            r.raise_for_status()
            data = r.json()
            if "access_token" not in data:
                raise RuntimeError(f"Token request failed: {data}")
            self._token = data["access_token"]
            self._token_expires = now + data.get("expires_in", 2592000)
            log.info("[baidu-ocr] token refreshed, expires in %ds", data.get("expires_in", 0))
            return self._token

    def _auth_url(self, base: str) -> str:
        return f"{base}?access_token={self._get_token()}"

    # ── General OCR (sync) ───────────────────────────────────

    def ocr_general(self, image_data: bytes, high_precision: bool = True) -> list:
        """Run general OCR on raw image bytes. Returns list of text lines.

        Args:
            image_data: raw image bytes (jpg/png/bmp)
            high_precision: use accurate_basic (higher accuracy) if True
        """
        url = self.GENERAL_ACCURATE_URL if high_precision else self.GENERAL_URL
        b64 = base64.b64encode(image_data).decode()
        r = _req.post(
            self._auth_url(url),
            data={"image": b64},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=self.timeout,
        )
        r.raise_for_status()
        data = r.json()
        if "error_code" in data and data["error_code"] != 0:
            raise RuntimeError(f"Baidu OCR error {data['error_code']}: {data.get('error_msg', '')}")
        return [w.get("words", "") for w in data.get("words_result", [])]

    def ocr_web_image(self, image_data: bytes) -> list:
        """OCR on web/network images (handles watermarks, complex backgrounds)."""
        b64 = base64.b64encode(image_data).decode()
        r = _req.post(
            self._auth_url(self.WEB_IMAGE_URL),
            data={"image": b64},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=self.timeout,
        )
        r.raise_for_status()
        data = r.json()
        if "error_code" in data and data["error_code"] != 0:
            raise RuntimeError(f"Baidu OCR error {data['error_code']}: {data.get('error_msg', '')}")
        return [w.get("words", "") for w in data.get("words_result", [])]

    def ocr_table(self, image_data: bytes) -> str:
        """Table OCR — returns HTML table from image."""
        b64 = base64.b64encode(image_data).decode()
        r = _req.post(
            self._auth_url(self.TABLE_URL),
            data={"image": b64},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=self.timeout,
        )
        r.raise_for_status()
        data = r.json()
        if "error_code" in data and data["error_code"] != 0:
            raise RuntimeError(f"Baidu OCR error {data['error_code']}: {data.get('error_msg', '')}")
        return data.get("result", {}).get("html", "")

    # ── Unlimited-OCR document parsing (async) ───────────────

    def parse_document(self, file_path: str) -> str:
        """Parse a document (PDF, DOC, image) → Markdown text.

        Uses the Unlimited-OCR async API:
          1. Submit file → get task_id
          2. Poll until status == 'success' → get markdown_url
          3. Download markdown content

        Args:
            file_path: local path to document (pdf/doc/docx/jpg/png/tif/etc.)

        Returns:
            Markdown-formatted text of the document content.
        """
        task_id = self._submit_document(file_path)
        log.info("[baidu-ocr] submitted %s → task_id=%s", os.path.basename(file_path), task_id)
        result = self._poll_task(task_id)
        md_url = result.get("markdown_url", "")
        if md_url:
            return self._download_markdown(md_url)
        raise RuntimeError(f"Baidu Unlimited-OCR: no markdown_url in result: {result}")

    def parse_document_from_url(self, file_url: str, file_name: str = "document.pdf") -> str:
        """Parse a document from URL → Markdown text."""
        task_id = self._submit_document_url(file_url, file_name)
        log.info("[baidu-ocr] submitted URL → task_id=%s", task_id)
        result = self._poll_task(task_id)
        md_url = result.get("markdown_url", "")
        if md_url:
            return self._download_markdown(md_url)
        raise RuntimeError(f"Baidu Unlimited-OCR: no markdown_url in result: {result}")

    def _submit_document(self, file_path: str) -> str:
        """Submit local file for parsing. Returns task_id.

        Supports all UTF text formats (UTF-8, UTF-16, UTF-32, with/without BOM)
        and binary document formats (PDF, DOC, DOCX, PPT, PPTX, XLS, XLSX, images).
        Text files are normalized to UTF-8 before submission.
        """
        file_path = os.path.expanduser(file_path)
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        file_size = os.path.getsize(file_path)
        if file_size > MAX_FILE_SIZE:
            raise ValueError(f"File too large: {file_size / 1024 / 1024:.1f}MB (max 100MB)")
        file_name = os.path.basename(file_path)
        ext = os.path.splitext(file_path)[1].lower()
        log.info("[baidu-ocr] submitting %s (%.1fMB, ext=%s)", file_name, file_size / 1024 / 1024, ext)

        # Read file and normalize text encodings to UTF-8
        with open(file_path, "rb") as f:
            raw = f.read()
        raw = _normalize_to_utf8(raw, ext)

        # Determine MIME type
        content_type = MIME_TYPES.get(ext, "application/octet-stream")

        # Submit via multipart with proper content type
        r = _req.post(
            self._auth_url(self.UNLIMITED_SUBMIT_URL),
            files={"file": (file_name, raw, content_type)},
            timeout=self.timeout,
        )
        resp = r.json()
        self._check_response(resp, "submit")
        task_id = resp.get("result", {}).get("task_id", "")
        if not task_id:
            raise RuntimeError(f"Baidu submit: no task_id in response: {resp}")
        return task_id

    def _submit_document_url(self, file_url: str, file_name: str = "") -> str:
        """Submit URL document for parsing. Returns task_id."""
        if not file_name:
            file_name = file_url.rsplit("/", 1)[-1] or "document.pdf"
        data = {"file_url": file_url, "file_name": file_name}
        r = _req.post(
            self._auth_url(self.UNLIMITED_SUBMIT_URL),
            data=data,
            timeout=self.timeout,
        )
        resp = r.json()
        self._check_response(resp, "submit-url")
        task_id = resp.get("result", {}).get("task_id", "")
        if not task_id:
            raise RuntimeError(f"Baidu submit-url: no task_id in response: {resp}")
        return task_id

    def _poll_task(self, task_id: str) -> dict:
        """Poll task until success/failure. Returns final result dict."""
        for attempt in range(self.max_polls):
            time.sleep(self.poll_interval)
            r = _req.post(
                self._auth_url(self.UNLIMITED_QUERY_URL),
                data={"task_id": task_id},
                timeout=60,
            )
            resp = r.json()
            self._check_response(resp, "poll")
            result = resp.get("result", {})
            status = result.get("status", "unknown")
            if status == "success":
                log.info("[baidu-ocr] task %s completed after %d polls", task_id, attempt + 1)
                return result
            if status in ("failed", "error"):
                error_msg = result.get("task_error") or result.get("error_msg", "unknown")
                raise RuntimeError(f"Baidu Unlimited-OCR task failed: {error_msg}")
            log.debug("[baidu-ocr] task %s status=%s, poll %d/%d", task_id, status, attempt + 1, self.max_polls)
        raise TimeoutError(f"Baidu Unlimited-OCR task {task_id} timed out after {self.max_polls} polls")

    def _download_markdown(self, url: str) -> str:
        """Download markdown content from URL with full UTF encoding support.

        Handles UTF-8, UTF-16, UTF-32, with or without BOM.
        Also handles gzip/deflate compressed responses.
        """
        r = _req.get(url, timeout=60, allow_redirects=True)
        r.raise_for_status()

        raw = r.content

        # Detect encoding from Content-Type header first
        ct = r.headers.get("Content-Type", "")
        if "charset=" in ct:
            charset = ct.split("charset=")[-1].strip().split(";")[0].strip()
            if charset and charset.lower() not in ("", "none"):
                try:
                    return raw.decode(charset)
                except (UnicodeDecodeError, LookupError):
                    pass

        # Detect from BOM
        enc = _detect_encoding(raw)
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            pass

        # Fallback: try UTF-8 with replacement
        return raw.decode("utf-8", errors="replace")

    # ── Batch processing ─────────────────────────────────────

    def parse_documents(self, file_paths: list, delay: float = 1.0) -> list:
        """Parse multiple documents. Returns list of (path, markdown_text) tuples.

        Args:
            file_paths: list of file paths
            delay: seconds between submissions (QPS limit: 2 for submit)
        """
        results = []
        task_ids = []
        for fp in file_paths:
            try:
                tid = self._submit_document(fp)
                task_ids.append((fp, tid))
                log.info("[baidu-ocr] submitted %s → %s", fp, tid)
            except Exception as e:
                log.error("[baidu-ocr] submit failed for %s: %s", fp, e)
                task_ids.append((fp, None))
            if delay > 0:
                time.sleep(delay)

        for fp, tid in task_ids:
            if tid is None:
                results.append((fp, "[SUBMIT FAILED]"))
                continue
            try:
                result = self._poll_task(tid)
                md_url = result.get("markdown_url", "")
                md_text = self._download_markdown(md_url) if md_url else ""
                results.append((fp, md_text))
            except Exception as e:
                log.error("[baidu-ocr] poll failed for %s: %s", fp, e)
                results.append((fp, f"[POLL FAILED: {e}]"))

        return results

    def ocr_images(self, image_paths: list, high_precision: bool = True) -> list:
        """OCR multiple images. Returns list of (path, text_lines) tuples."""
        results = []
        for fp in image_paths:
            try:
                with open(fp, "rb") as f:
                    data = f.read()
                lines = self.ocr_general(data, high_precision=high_precision)
                results.append((fp, lines))
            except Exception as e:
                log.error("[baidu-ocr] image OCR failed for %s: %s", fp, e)
                results.append((fp, [f"[FAILED: {e}]"]))
        return results

    # ── Status check ─────────────────────────────────────────

    def status(self) -> dict:
        """Return provider status and remaining quota info."""
        return {
            "provider": "baidu_ocr",
            "configured": bool(self.api_key and self.secret_key),
            "endpoints": {
                "unlimited_ocr": "Unlimited document parsing (PDF/DOC/images → Markdown)",
                "general_basic": "Standard OCR (1000 free/month personal)",
                "accurate_basic": "High-precision OCR (1000 free/month personal)",
                "web_image": "Web image OCR (1000 free/month personal)",
                "table": "Table OCR V2 (500 free/month personal)",
            },
            "free_tiers": {
                "unlimited_ocr": "200 pages/personal, 1000 pages/enterprise",
                "general_ocr": "1000 calls/month/personal, 2000/month/enterprise",
                "web_image": "1000 calls/month/personal",
                "table": "500 calls/month/personal",
            },
            "supports": ["pdf", "doc", "docx", "ppt", "pptx", "txt", "wps",
                         "jpg", "jpeg", "png", "bmp", "tif", "tiff", "ofd"],
            "max_file_size_mb": 100,
            "max_pdf_pages": 500,
        }
