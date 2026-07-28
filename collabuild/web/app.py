"""Collabuild MAS — KoboldCPP-style web UI.

Chat interface with local model support (GGUF/GGML), Ollama, KoboldCPP,
OpenRouter, NVIDIA Build, and custom OpenAI-compatible endpoints.
"""

import asyncio
import json
import logging
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from .. import config as cfgmod
from ..providers import (
    PROVIDER_REGISTRY,
    LLMProvider,
    create_provider,
    discover_local_models,
)

log = logging.getLogger("collabuild.web")

# ── App setup ──────────────────────────────────────────────
HERE = Path(__file__).parent
templates = Jinja2Templates(directory=str(HERE / "templates"))

app = FastAPI(title="Collabuild MAS", version="1.0.0")

# In-memory state
chat_sessions: dict = {}
active_providers: dict = {}
user_settings: dict = {}


# ── Load saved settings ────────────────────────────────────
def _load_settings() -> dict:
    settings_path = HERE / "settings.json"
    if settings_path.exists():
        try:
            return json.loads(settings_path.read_text())
        except Exception:
            pass
    return {}


def _save_settings(settings: dict):
    settings_path = HERE / "settings.json"
    settings_path.write_text(json.dumps(settings, indent=2))


user_settings = _load_settings()


# ── Get or create provider from settings ───────────────────
def _get_provider(settings: dict = None) -> LLMProvider:
    s = settings or user_settings
    # Start with config.yaml defaults, then overlay user settings
    try:
        full_cfg = cfgmod.load()
        cfg = cfgmod.get_ai_config(full_cfg)
    except Exception:
        cfg = {}
    # User settings override config.yaml
    for key in ("provider", "endpoint", "api_key", "model"):
        val = s.get(key, "")
        if val:
            cfg[key] = val
    if not cfg.get("provider"):
        cfg["provider"] = "openrouter"
    return create_provider(cfg)


# ═══════════════════════════════════════════════════════════════
# ROUTES — Main UI
# ═══════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("chat.html", {
        "request": request,
        "settings": user_settings,
    })


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "settings": user_settings,
        "providers": list(PROVIDER_REGISTRY.keys()),
    })


@app.get("/pipeline", response_class=HTMLResponse)
async def pipeline_page(request: Request):
    """Legacy pipeline page."""
    cfg = cfgmod.load()
    providers = list(cfg.get("providers", {}).keys())
    if not providers:
        providers = list(PROVIDER_REGISTRY.keys())
    stages = [
        "Paper Analysis", "SRS Generation", "Module Design", "User Flow Design",
        "SDLC Plan", "Code Generation", "Debugging & Review", "Deployment Plan", "Final Review"
    ]
    return templates.TemplateResponse("pipeline.html", {
        "request": request,
        "providers": providers,
        "stages": stages,
    })


# ═══════════════════════════════════════════════════════════════
# API — Chat (streaming)
# ═══════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    messages: list
    model: str = ""
    provider: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 0.9
    top_k: int = 40
    repeat_penalty: float = 1.1
    system_prompt: str = ""


@app.post("/api/chat")
async def api_chat(req: ChatRequest):
    provider_name = req.provider or user_settings.get("provider", "openrouter")
    model = req.model or user_settings.get("model", "")

    # Build messages with system prompt
    messages = list(req.messages)
    sys_prompt = req.system_prompt or user_settings.get("system_prompt", "")
    if sys_prompt and (not messages or messages[0].get("role") != "system"):
        messages.insert(0, {"role": "system", "content": sys_prompt})

    # Get provider
    settings = {**user_settings, "provider": provider_name}
    if req.provider:
        settings["provider"] = req.provider

    try:
        provider = _get_provider(settings)
    except Exception as e:
        return JSONResponse({"error": f"Failed to create provider: {e}"}, status_code=500)

    if not model:
        model = user_settings.get("model", "")

    # Streaming response
    async def stream():
        try:
            loop = asyncio.get_event_loop()
            queue = asyncio.Queue()

            def _gen():
                try:
                    for token in provider.chat_stream(
                        model=model, messages=messages,
                        temperature=req.temperature, max_tokens=req.max_tokens,
                    ):
                        loop.call_soon_threadsafe(queue.put_nowait, token)
                except Exception as e:
                    loop.call_soon_threadsafe(queue.put_nowait, f"[Error: {e}]")
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, None)

            import concurrent.futures
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            executor.submit(_gen)

            while True:
                token = await queue.get()
                if token is None:
                    break
                yield {"event": "token", "data": token}
            yield {"event": "done", "data": ""}
            executor.shutdown(wait=False)
        except Exception as e:
            yield {"event": "error", "data": str(e)}

    return EventSourceResponse(stream())


@app.post("/api/chat/sync")
async def api_chat_sync(req: ChatRequest):
    """Non-streaming chat endpoint."""
    provider_name = req.provider or user_settings.get("provider", "openrouter")
    model = req.model or user_settings.get("model", "")

    messages = list(req.messages)
    sys_prompt = req.system_prompt or user_settings.get("system_prompt", "")
    if sys_prompt and (not messages or messages[0].get("role") != "system"):
        messages.insert(0, {"role": "system", "content": sys_prompt})

    settings = {**user_settings, "provider": provider_name}
    if req.provider:
        settings["provider"] = req.provider

    try:
        provider = _get_provider(settings)
        result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: provider.chat(model=model, messages=messages,
                                         temperature=req.temperature, max_tokens=req.max_tokens)
        )
        return {"response": result}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ═══════════════════════════════════════════════════════════════
# API — Settings & Models
# ═══════════════════════════════════════════════════════════════

@app.get("/api/settings")
async def api_get_settings():
    return user_settings


@app.post("/api/settings")
async def api_save_settings(request: Request):
    data = await request.json()
    user_settings.update(data)
    _save_settings(user_settings)
    return {"ok": True, "settings": user_settings}


@app.get("/api/models")
async def api_list_models(provider: str = ""):
    provider_name = provider or user_settings.get("provider", "openrouter")
    settings = {**user_settings, "provider": provider_name}
    try:
        p = _get_provider(settings)
        models = await asyncio.get_event_loop().run_in_executor(None, p.list_models)
        return {"models": models, "provider": provider_name}
    except Exception as e:
        return {"models": [], "error": str(e), "provider": provider_name}


@app.get("/api/local-models")
async def api_local_models():
    search_paths = user_settings.get("model_search_paths", None)
    models = discover_local_models(search_paths)
    return {"models": models}


@app.get("/api/providers/status")
async def api_provider_status():
    """Check which providers are reachable."""
    statuses = {}
    for name in ["ollama", "koboldcpp", "textgen"]:
        settings = {**user_settings, "provider": name}
        try:
            p = _get_provider(settings)
            endpoint = getattr(p, "endpoint", "")
            if not endpoint:
                statuses[name] = {"status": "no_endpoint"}
                continue
            import requests
            r = requests.get(endpoint, timeout=3)
            statuses[name] = {"status": "online", "endpoint": endpoint, "code": r.status_code}
        except Exception as e:
            statuses[name] = {"status": "offline", "error": str(e)}
    return statuses


# ═══════════════════════════════════════════════════════════════
# API — Pipeline (legacy, kept for backward compat)
# ═══════════════════════════════════════════════════════════════

runs: dict = {}

SAMPLE_PAPER = """Unlimited OCR Works: Welcome the Era of One-shot Long-horizon Parsing

Authors: Youyang Yin, Huanhuan Liu, et al. — Baidu Inc.

Abstract: This paper introduces Unlimited-OCR, a novel approach to document parsing that
handles long-form documents in a single forward pass. Unlike traditional OCR systems that
process pages sequentially or chunk documents, Unlimited-OCR uses a vision-language model
with a 32K context window to parse entire documents end-to-end. The model supports two
inference modes: 'gundam' (base_size=1024, image_size=640, crop_mode=True) for detailed
single-page parsing, and 'base' (base_size=1024, image_size=1024, crop_mode=False) for
multi-page documents. Key innovations include: (1) a no-repeat n-gram constraint to prevent
hallucinated repetitions in long outputs, (2) adaptive cropping that preserves document
structure across page boundaries, and (3) a custom logit processor for controlled generation."""


@app.post("/api/pipeline/run")
async def pipeline_start(request: Request):
    data = await request.json()
    paper = data.get("paper", SAMPLE_PAPER)
    provider_name = data.get("provider", user_settings.get("provider", "openrouter"))
    model = data.get("model", user_settings.get("model", ""))

    run_id = uuid.uuid4().hex[:12]
    runs[run_id] = {
        "status": "running", "progress": 0, "current_stage": "",
        "results": {}, "report": "", "error": "",
    }

    asyncio.create_task(_run_pipeline_bg(run_id, paper, provider_name, model))
    return {"run_id": run_id}


@app.get("/api/pipeline/{run_id}")
async def pipeline_status(run_id: str):
    run = runs.get(run_id)
    if not run:
        return JSONResponse({"error": "not found"}, 404)
    return run


@app.get("/api/pipeline/{run_id}/stream")
async def pipeline_stream(run_id: str):
    async def gen():
        last = -1
        while True:
            r = runs.get(run_id)
            if not r:
                yield {"event": "error", "data": "deleted"}
                break
            if r["status"] == "complete":
                yield {"event": "complete", "data": json.dumps({"run_id": run_id})}
                break
            if r["status"] == "error":
                yield {"event": "error", "data": json.dumps({"error": r["error"]})}
                break
            if r["progress"] != last:
                last = r["progress"]
                yield {"event": "progress", "data": json.dumps({
                    "progress": r["progress"], "stage": r["current_stage"],
                    "stage_index": r.get("stage_index", 0),
                })}
            await asyncio.sleep(0.5)
    return EventSourceResponse(gen())


async def _run_pipeline_bg(run_id: str, paper: str, provider_name: str, model: str):
    loop = asyncio.get_event_loop()
    run = runs[run_id]
    try:
        from ..pipeline import CollabuildPipeline
        settings = {**user_settings, "provider": provider_name}
        if model:
            settings["model"] = model
        provider = _get_provider(settings)
        pipeline = CollabuildPipeline(provider=provider, model=model or "")

        def progress_run(paper_text):
            stage_names = [
                ("paper_analysis", "Paper Analysis"), ("srs", "SRS Generation"),
                ("module_design", "Module Design"), ("user_flow", "User Flow Design"),
                ("sdlc_plan", "SDLC Plan"), ("code_gen", "Code Generation"),
                ("debug", "Debugging & Review"), ("deployment", "Deployment Plan"),
                ("final_review", "Final Review"),
            ]
            results = {}
            prev = ""
            for idx, (key, label) in enumerate(stage_names):
                run["current_stage"] = label
                run["stage_index"] = idx
                run["progress"] = int((idx / len(stage_names)) * 100)
                stage = pipeline.stages[key]
                if key == "paper_analysis":
                    r = stage.run(paper_text)
                elif key == "srs" or key in ("module_design", "user_flow"):
                    r = stage.run(prev)
                elif key == "sdlc_plan":
                    r = stage.run(results.get("module_design", ""), results.get("user_flow", ""))
                elif key == "code_gen":
                    r = stage.run(results.get("module_design", ""), results.get("user_flow", ""), results.get("sdlc_plan", ""))
                elif key == "debug":
                    r = stage.run(prev)
                elif key == "deployment":
                    r = stage.run(prev, results.get("debug", ""))
                elif key == "final_review":
                    flat = {k: str(v.content)[:500] for k, v in results.items()}
                    r = stage.run(flat)
                else:
                    r = stage.run(prev)
                results[key] = r
                prev = r.content
            run["results"] = {k: {
                "stage": v.stage, "agent": v.agent,
                "content": v.content[:2000], "mermaid": v.mermaid, "passed": v.passed,
            } for k, v in results.items()}
            run["report"] = pipeline.report()
            run["status"] = "complete"
            run["progress"] = 100

        pipeline.run = progress_run
        await loop.run_in_executor(None, pipeline.run, paper)
    except Exception as e:
        log.exception("Pipeline failed")
        run["status"] = "error"
        run["error"] = str(e)


# ═══════════════════════════════════════════════════════════════
# API — Tools (OCR, Web Fetcher, Agent Runner)
# ═══════════════════════════════════════════════════════════════

@app.get("/tools", response_class=HTMLResponse)
async def tools_page(request: Request):
    """Research tools page — OCR, web fetcher, agent runner."""
    return templates.TemplateResponse("tools.html", {
        "request": request,
        "settings": user_settings,
    })


@app.get("/api/tools/status")
async def api_tools_status():
    """Status of all research tools."""
    statuses = {}
    # Web fetcher
    try:
        from ..research.web_fetcher import WebFetcher
        wf = WebFetcher()
        statuses["web_fetcher"] = wf.status()
    except Exception as e:
        statuses["web_fetcher"] = {"error": str(e)}

    # OCR
    try:
        from ..ocr.baidu_ocr import BaiduOCR
        ocr = BaiduOCR()
        statuses["ocr"] = ocr.status()
    except Exception as e:
        statuses["ocr"] = {"error": str(e)}

    # Agent runner
    try:
        from ..research.agent_runner import AgentRunner
        ar = AgentRunner()
        statuses["agent_runner"] = ar.status()
    except Exception as e:
        statuses["agent_runner"] = {"error": str(e)}

    return statuses


@app.post("/api/tools/ocr")
async def api_ocr_file(request: Request):
    """OCR a file via Baidu Unlimited-OCR or general OCR."""
    data = await request.json()
    file_path = data.get("file_path", "")
    mode = data.get("mode", "document")  # "document" or "image"

    if not file_path:
        return JSONResponse({"error": "file_path required"}, 400)

    try:
        from ..ocr.baidu_ocr import BaiduOCR
        ocr = BaiduOCR()

        if mode == "document":
            text = await asyncio.get_event_loop().run_in_executor(
                None, ocr.parse_document, file_path
            )
        else:
            with open(file_path, "rb") as f:
                img_data = f.read()
            lines = await asyncio.get_event_loop().run_in_executor(
                None, lambda: ocr.ocr_general(img_data)
            )
            text = "\n".join(lines)

        return {"text": text, "file_path": file_path, "mode": mode}
    except Exception as e:
        return JSONResponse({"error": str(e)}, 500)


@app.post("/api/tools/web-fetch")
async def api_web_fetch(request: Request):
    """Fetch and extract text from a URL."""
    data = await request.json()
    url = data.get("url", "")
    if not url:
        return JSONResponse({"error": "url required"}, 400)

    try:
        from ..research.web_fetcher import WebFetcher
        wf = WebFetcher()
        result = await asyncio.get_event_loop().run_in_executor(
            None, wf.fetch_url, url
        )
        return result
    except Exception as e:
        return JSONResponse({"error": str(e)}, 500)


@app.post("/api/tools/agent-run")
async def api_agent_run(request: Request):
    """Run an autonomous research agent task."""
    data = await request.json()
    task = data.get("task", "")
    context = data.get("context", "")
    if not task:
        return JSONResponse({"error": "task required"}, 400)

    try:
        from ..research.agent_runner import AgentRunner
        from ..research.web_fetcher import WebFetcher

        provider = _get_provider()
        web_fetcher = WebFetcher()

        def _run_agent():
            from ..ocr.baidu_ocr import BaiduOCR
            ocr = BaiduOCR()
            ar = AgentRunner(
                llm_chat=provider.chat,
                llm_model=user_settings.get("model", ""),
                web_fetcher=web_fetcher,
                ocr_client=ocr,
            )
            return ar.run(task, context)

        result = await asyncio.get_event_loop().run_in_executor(None, _run_agent)

        return {
            "task": result.task,
            "final_answer": result.final_answer,
            "steps": [{"step_num": s.step_num, "thought": s.thought,
                       "tool_calls": [{"tool": tc.tool, "args": tc.args,
                                       "success": tc.success, "duration_ms": tc.duration_ms}
                                      for tc in s.tool_calls],
                       "output": s.output[:500]} for s in result.steps],
            "total_tool_calls": result.total_tool_calls,
            "total_duration_ms": result.total_duration_ms,
            "success": result.success,
            "error": result.error,
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, 500)
