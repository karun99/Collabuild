"""OCR module — Baidu OCR unlimited document parsing + agent-runner integration."""

from ..research.agent_runner import AgentRunner

from .baidu_ocr import BaiduOCR

__all__ = ["BaiduOCR", "create_ocr_agent_runner"]


def create_ocr_agent_runner(baidu_ocr: BaiduOCR | None = None, **kwargs) -> AgentRunner:
    """Create an AgentRunner pre-configured with OCR tools.

    The runner has the full toolset (web_fetch, ocr_file, ocr_image,
    python_exec, search) with BaiduOCR wired in.

    Args:
        baidu_ocr: BaiduOCR instance (created from config if None)
        **kwargs: passed through to AgentRunner (max_steps, timeout, etc.)

    Returns:
        AgentRunner with OCR capabilities
    """
    if baidu_ocr is None:
        api_key = kwargs.pop("api_key", "")
        secret_key = kwargs.pop("secret_key", "")
        timeout = kwargs.pop("ocr_timeout", 120)
        baidu_ocr = BaiduOCR(api_key=api_key, secret_key=secret_key, timeout=timeout)

    return AgentRunner(
        ocr_client=baidu_ocr,
        **kwargs,
    )
