# Collabuild MAS — Application Documentation

**Version:** 0.3.0
**Author:** [Sai Karun Nandipati](https://karun99.github.io)
**License:** MIT

---

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Core Components](#core-components)
4. [Provider System](#provider-system)
5. [Pipeline System](#pipeline-system)
6. [Web Application](#web-application)
7. [OCR Module](#ocr-module)
8. [Research Tools](#research-tools)
9. [Configuration System](#configuration-system)
10. [Dev Fallback Mechanism](#dev-fallback-mechanism)
11. [API Reference](#api-reference)
12. [Data Flow](#data-flow)
13. [Security Considerations](#security-considerations)
14. [Performance Characteristics](#performance-characteristics)
15. [Extension Points](#extension-points)

---

## 1. Overview

Collabuild MAS is a first-in-class fully customisable Multi-Agent System that bridges the gap between research papers and production-ready software. The application provides:

- **KoboldCPP-style chat UI** for conversing with AI models (local and cloud)
- **9-stage research paper to production pipeline** that transforms academic papers into deployable systems
- **7 LLM provider integrations** (OpenRouter, NVIDIA, Claude, Ollama, KoboldCPP, text-generation-webui, custom)
- **Baidu OCR integration** for document parsing (Unlimited-OCR + general OCR)
- **Autonomous research agent** with tool use (web fetch, OCR, code execution)
- **Dev fallback mechanism** for offline testing and pipeline verification

### Key Design Principles

1. **Provider Agnostic** — Any OpenAI-compatible endpoint works out of the box
2. **Offline Capable** — DevProvider enables full pipeline testing without network
3. **Extensible** — New providers, pipeline stages, and tools can be added
4. **Configurable** — YAML-based configuration with environment variable resolution
5. **Deployable** — Docker, GitHub Actions, and PyPI-ready

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Browser (Web UI)                          │
│  ┌──────────────┐  ┌─────────────────────────────────────┐  │
│  │    Sidebar    │  │          Chat Area                   │  │
│  │  • Provider   │  │  ┌─────────────────────────────┐   │  │
│  │  • Model      │  │  │  Messages (streamed via SSE) │   │  │
│  │  • Params     │  │  └─────────────────────────────┘   │  │
│  │  • GGUF scan  │  │  ┌─────────────────────────────┐   │  │
│  │  • Nav links  │  │  │  Input bar (auto-resize)     │   │  │
│  └──────────────┘  │  └─────────────────────────────┘   │  │
│                     └─────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────┘
                            │ SSE / JSON API
┌───────────────────────────▼─────────────────────────────────┐
│               FastAPI Backend (app.py)                        │
│  /api/chat (SSE)  /api/settings  /api/models                 │
│  /api/local-models  /api/providers/status                     │
│  /api/pipeline/*  /api/chat/sync                              │
│  /api/tools/*  (OCR, Web Fetch, Agent Runner)                 │
└──────┬────────────┬────────────┬────────────┬───────────────┘
       │            │            │            │
┌──────▼──┐ ┌──────▼──┐ ┌──────▼──┐ ┌──────▼──┐
│OpenRouter│ │ NVIDIA  │ │ Claude  │ │ Ollama  │  ...
│  (cloud) │ │  Build  │ │ (cloud) │ │ (local) │
└──────────┘ └─────────┘ └─────────┘ └─────────┘
       │            │            │            │
┌──────▼──┐ ┌──────▼──┐ ┌──────▼──┐ ┌──────▼──┐
│KoboldCPP│ │ textgen  │ │  Dev    │ │ Custom  │
│ (local) │ │ (local)  │ │ (mock)  │ │ (any)   │
└──────────┘ └─────────┘ └─────────┘ └─────────┘
```

### Module Dependency Graph

```
collabuild/
├── __init__.py          → Exports pipeline, mas, providers
├── __main__.py          → CLI entry point, argument parsing
├── config.py            → YAML loading, env var resolution
├── providers.py         → LLM provider classes + factory
├── mas.py               → Agent, Crew, Task, OCRAgent
├── pipeline.py          → 9-stage pipeline orchestrator
├── ocr/
│   └── baidu_ocr.py     → Baidu OCR client
├── research/
│   ├── web_fetcher.py   → HTML/text content extractor
│   └── agent_runner.py  → Autonomous research agent
└── web/
    ├── app.py           → FastAPI application
    └── templates/       → Jinja2 HTML templates
```

---

## 3. Core Components

### 3.1 Providers (`providers.py`)

The provider system is built on an abstract base class `LLMProvider` with a factory pattern for instantiation.

**Class Hierarchy:**

```
LLMProvider (ABC)
├── OpenAICompatibleProvider
│   ├── OpenRouterProvider      (openrouter.ai)
│   ├── NvidiaProvider          (integrate.api.nvidia.com)
│   └── TextGenWebUIProvider    (localhost:5000)
├── ClaudeProvider              (api.anthropic.com)
├── OllamaProvider              (localhost:11434)
├── KoboldCPPProvider           (localhost:5001)
└── DevProvider                 (offline mock)
```

**Required Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `chat()` | `(model, messages, temperature, max_tokens) -> str` | Non-streaming completion |
| `chat_stream()` | `(model, messages, temperature, max_tokens) -> Iterator[str]` | Token-by-token streaming |
| `list_models()` | `() -> list` | Available model names |

**Factory Usage:**

```python
from collabuild.providers import create_provider

# Create any provider from a config dict
provider = create_provider({
    "provider": "openrouter",
    "api_key": "sk-or-...",
    "endpoint": "https://openrouter.ai/api/v1"
})

# Dev mode (no API key needed)
provider = create_provider({"provider": "dev"})
```

### 3.2 Pipeline (`pipeline.py`)

The pipeline orchestrates 9 sequential stages, each powered by a `StageAgent` that uses an `LLMProvider`.

**Stage Classes:**

| Stage | Class | Input | Output |
|-------|-------|-------|--------|
| 1. Paper Analysis | `PaperAnalyzer` | Paper text | Structured analysis + Mermaid flowchart |
| 2. SRS Generation | `SRSGenerator` | Analysis | IEEE 830 SRS document |
| 3. Module Design | `ModuleDesigner` | SRS | Module architecture + class diagram |
| 4. User Flow | `UserFlowDesigner` | Modules | UX flows + sequence diagrams |
| 5. SDLC Plan | `SDLCPlanner` | Modules + Flows | Project plan + Gantt chart |
| 6. Code Generation | `CodeGenerator` | Modules + Flows + SDLC | Production-ready code |
| 7. Debug & Review | `Debugger` | Code | Bug report + fixes |
| 8. Deployment | `DeploymentPlanner` | Code + Review | Infrastructure plan + diagram |
| 9. Final Review | `FinalReviewer` | All results | QA validation (PASS/FAIL) |

**Pipeline Execution:**

```python
from collabuild.pipeline import CollabuildPipeline
from collabuild.providers import DevProvider

pipeline = CollabuildPipeline(provider=DevProvider())
results = pipeline.run("Your research paper text here...")

# Generate report
report = pipeline.report()
```

### 3.3 Multi-Agent System (`mas.py`)

A CrewAI-like framework for configuring and running AI agents.

**Core Classes:**

- `Agent` — Wraps an LLM provider with a specific role and configuration
- `Crew` — Manages a collection of agents and executes tasks
- `Task` — Defines a unit of work with dependencies and callbacks
- `AgentConfig` — Configuration dataclass with auth, endpoint, and model settings
- `OCRAgent` — Specialized agent for document parsing via vision APIs

**Process Types:**

| Type | Description |
|------|-------------|
| `SEQUENTIAL` | Tasks run one after another, injecting prior results |
| `PARALLEL` | Tasks run concurrently in a thread pool |
| `HIERARCHICAL` | A manager agent orchestrates task execution |

---

## 4. Provider System

### 4.1 OpenRouter

Cloud API with 200+ models. Free tier available.

- **Endpoint:** `https://openrouter.ai/api/v1`
- **Auth:** API key (`OPENROUTER_API_KEY` env var)
- **Streaming:** Full SSE support
- **Model Discovery:** Auto-fetched from `/v1/models`

### 4.2 NVIDIA Build

Cloud API with 160+ open models from NVIDIA.

- **Endpoint:** `https://integrate.api.nvidia.com/v1`
- **Auth:** API key (`NVIDIA_API_KEY` env var)
- **Streaming:** Full SSE support

### 4.3 Anthropic Claude

Native Messages API — no SDK dependency.

- **Endpoint:** `https://api.anthropic.com/v1`
- **Auth:** API key (`ANTHROPIC_API_KEY` env var)
- **Streaming:** SSE with `content_block_delta` events
- **Models:** claude-opus-4-8, claude-sonnet-4-20250514, claude-haiku-4-5-20251001

### 4.4 Ollama

Local LLM inference server.

- **Endpoint:** `http://localhost:11434`
- **Auth:** None
- **Streaming:** Native JSON streaming
- **Model Discovery:** Auto-fetched from `/api/tags`

### 4.5 KoboldCPP

Local GGUF model runner.

- **Endpoint:** `http://localhost:5001`
- **Auth:** None
- **Streaming:** Supported via `/api/v1/generate` with `stream: true`
- **Model Discovery:** Returns currently loaded model

### 4.6 text-generation-webui (oobabooga)

Local LLM server with OpenAI-compatible API.

- **Endpoint:** `http://localhost:5000`
- **Auth:** None
- **Streaming:** Full SSE via `/v1/chat/completions`
- **Model Discovery:** Auto-fetched from `/v1/models`

### 4.7 DevProvider (Offline Mock)

Returns structured mock responses for each pipeline stage. No API key or network required.

- **Activation:** `collabuild --dev` or `create_provider({"provider": "dev"})`
- **Purpose:** Offline testing, CI/CD, pipeline verification
- **Output:** Realistic mock responses with Mermaid diagrams

### 4.8 Custom Provider

Any endpoint implementing the OpenAI `/v1/chat/completions` specification.

- vLLM, llama.cpp server, LocalAI, LM Studio, etc.
- Set endpoint URL and API key in settings

---

## 5. Pipeline System

### 5.1 Stage Execution Flow

```
Paper Text → [1] Paper Analysis → Analysis + Mermaid
                                      │
                                      ▼
                                [2] SRS Generation → SRS Document
                                      │
                                      ▼
                                [3] Module Design → Architecture
                                      │
                                      ▼
                                [4] User Flow → UX Diagrams
                                      │
                                      ▼
                                [5] SDLC Plan → Project Timeline
                                      │
                                      ▼
                                [6] Code Gen → Source Code
                                      │
                                      ▼
                                [7] Debug Review → Bug Report
                                      │
                                      ▼
                                [8] Deployment → Infrastructure
                                      │
                                      ▼
                                [9] Final Review → QA Report
```

### 5.2 StageResult Dataclass

```python
@dataclass
class StageResult:
    stage: str          # Stage name (e.g., "Paper Analysis")
    agent: str          # Agent name (e.g., "Paper-Analyzer")
    content: str        # Full LLM output
    mermaid: str = ""   # Extracted Mermaid diagram code
    artifacts: dict = field(default_factory=dict)
    passed: bool = True # Whether the stage succeeded
    notes: str = ""
```

### 5.3 Error Handling

- `StageAgent.call()` catches all exceptions and returns `Error: {message}`
- `StageAgent._last_error` tracks whether the last call succeeded
- `StageResult.passed` is set to `False` when `_last_error is not None`
- The `FinalReviewer` stage checks for "FAIL" in its content

### 5.4 Dev Mode Pipeline

When using `DevProvider`, the pipeline runs entirely offline:

1. Each stage receives a prompt matching its system prompt keywords
2. The DevProvider returns a pre-built response for that stage
3. All 9 stages complete with `passed=True`
4. Mermaid diagrams are included in every response
5. The full pipeline report is generated

---

## 6. Web Application

### 6.1 Pages

| Page | URL | Description |
|------|-----|-------------|
| Chat | `/` | Main chat interface (KoboldCPP-style) |
| Settings | `/settings` | Provider config, chat params, model paths |
| Pipeline | `/pipeline` | 9-stage pipeline runner with progress |
| Tools | `/tools` | OCR, web fetcher, agent runner |

### 6.2 Chat Interface Features

- Real-time streaming via Server-Sent Events (SSE)
- Stop generation mid-response
- Export chat to Markdown
- Markdown rendering (code blocks, bold, italic)
- Mobile-responsive (sidebar collapses to hamburger)
- Provider/model switching without page reload

### 6.3 Settings Page

- Provider selector with endpoint/API key fields
- Chat parameter sliders (temperature, max tokens, top_p, top_k, repeat penalty)
- System prompt editor
- Local model search path configuration
- Provider status checker (online/offline)

### 6.4 Pipeline Page

- Provider/model selection
- Paper text input (textarea or file upload)
- Real-time progress bar with stage-by-stage updates
- Mermaid diagram rendering
- Full report generation and download

### 6.5 Tools Page

- **OCR:** Upload document → parse via Baidu Unlimited-OCR
- **Web Fetcher:** Enter URL → extract clean text content
- **Agent Runner:** Enter task → autonomous research with tool use

---

## 7. OCR Module

### 7.1 Baidu OCR Integration

**Endpoints:**

| Endpoint | Purpose | Free Tier |
|----------|---------|-----------|
| Unlimited-OCR | Document parsing (PDF/DOC → Markdown) | 200 pages/personal |
| General Basic | Standard OCR | 1000 calls/month |
| Accurate Basic | High-precision OCR | 1000 calls/month |
| Web Image | Network image OCR | 1000 calls/month |
| Table OCR V2 | Table extraction | 500 calls/month |

**Auth Flow:**

1. POST to OAuth2 token endpoint with `client_id` + `client_secret`
2. Receive `access_token` (cached until expiry)
3. Include `?access_token=` in all subsequent API calls

**Supported Formats:**

PDF, DOC, DOCX, PPT, PPTX, TXT, WPS, JPG, JPEG, PNG, BMP, TIF, TIFF, OFD

### 7.2 Batch Processing

```python
from collabuild.ocr.baidu_ocr import BaiduOCR

ocr = BaiduOCR(api_key="...", secret_key="...")

# Parse multiple documents
results = ocr.parse_documents(["doc1.pdf", "doc2.pdf"], delay=1.0)

# OCR multiple images
results = ocr.ocr_images(["img1.jpg", "img2.png"])
```

---

## 8. Research Tools

### 8.1 Web Fetcher (`web_fetcher.py`)

Stdlib-only HTML-to-text extractor with caching.

**Features:**
- HTML → clean text extraction (skips scripts, styles, nav)
- PDF detection and handling
- Redirect following with rate limiting
- LRU cache (100 entries)
- Content summarization

**Usage:**

```python
from collabuild.research.web_fetcher import WebFetcher

wf = WebFetcher(timeout=30, max_retries=3)
result = wf.fetch_url("https://example.com")
# Returns: {url, status, title, text, word_count, is_pdf, ...}
```

### 8.2 Agent Runner (`agent_runner.py`)

Autonomous research agent with tool use.

**Available Tools:**

| Tool | Description | Args |
|------|-------------|------|
| `web_fetch` | Fetch URL and extract text | `{url: string}` |
| `ocr_file` | OCR a document file | `{file_path: string}` |
| `ocr_image` | OCR an image file | `{file_path: string}` |
| `python_exec` | Execute Python code (sandboxed) | `{code: string}` |
| `search` | Web search (placeholder) | `{query: string}` |

**Execution Loop:**

1. User provides task/query
2. LLM breaks task into sub-steps
3. Agent executes tool calls and collects results
4. LLM synthesizes findings
5. Returns structured `AgentResult`

---

## 9. Configuration System

### 9.1 Config File Structure

```yaml
providers:
  openrouter:
    endpoint: "https://openrouter.ai/api/v1"
    api_key: "${OPENROUTER_API_KEY}"
    model: "openrouter/free"
  # ... (6 more providers)

ocr:
  baidu:
    api_key: "${BAIDU_OCR_API_KEY}"
    secret_key: "${BAIDU_OCR_SECRET_KEY}"

web_fetcher:
  timeout: 30
  max_retries: 3

agent_runner:
  max_steps: 15
  max_tool_calls: 50

chat:
  system_prompt: "You are a helpful assistant."
  temperature: 0.7
  max_tokens: 4096

pipeline:
  provider: "openrouter"
  stages:
    paper_analysis:
      agent: "Paper-Analyzer"
      temperature: 0.3
```

### 9.2 Environment Variable Resolution

All `${VAR_NAME}` placeholders are resolved automatically:

```yaml
api_key: "${OPENROUTER_API_KEY}"  # Resolves to env var value
```

If the env var is not set, it resolves to an empty string.

### 9.3 Config Loading Priority

1. Custom path via `--config` flag
2. Bundled `config.yaml` in the package
3. Defaults (empty dict)

---

## 10. Dev Fallback Mechanism

### 10.1 Purpose

The DevProvider ensures that:
- Code developed is **clear** — mock responses have structured, readable output
- Code developed is **authentic** — responses match real pipeline stage expectations
- Code developed is **implementable** — full pipeline runs end-to-end offline

### 10.2 Activation Methods

```bash
# CLI
collabuild --dev                    # Pipeline with DevProvider
collabuild web --dev                # Web UI with DevProvider

# Config
pipeline:
  provider: "dev"

# Code
from collabuild.providers import DevProvider
provider = DevProvider()
```

### 10.3 Environment Variable

When `--dev` is used, `COLLABUILD_DEV_MODE=1` is set. The web app checks this:

```python
import os
if os.getenv("COLLABUILD_DEV_MODE") == "1":
    # Use DevProvider for all requests
    pass
```

### 10.4 Mock Response Structure

Each pipeline stage has a dedicated mock response that includes:
- Structured markdown content matching the stage's expected output
- Mermaid diagram code (flowcharts, sequence diagrams, class diagrams, Gantt charts)
- Realistic technical details (algorithms, architecture, deployment specs)

### 10.5 Streaming in Dev Mode

The DevProvider's `chat_stream()` splits responses into 3-word chunks, simulating token-by-token streaming for UI testing.

---

## 11. API Reference

### Chat Endpoints

| Endpoint | Method | Description | Response |
|----------|--------|-------------|----------|
| `/api/chat` | POST | Streaming chat | SSE (token events) |
| `/api/chat/sync` | POST | Non-streaming chat | JSON `{response}` |

### Settings Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/settings` | GET | Get current settings |
| `/api/settings` | POST | Save settings |
| `/api/models?provider=X` | GET | List models from provider |
| `/api/local-models` | GET | Scan for .gguf/.ggml files |
| `/api/providers/status` | GET | Check provider reachability |

### Pipeline Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/pipeline/run` | POST | Start pipeline run |
| `/api/pipeline/{run_id}` | GET | Get run status/results |
| `/api/pipeline/{run_id}/stream` | GET | SSE stream of progress |

### Tools Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/tools/status` | GET | Status of all research tools |
| `/api/tools/ocr` | POST | OCR a file via Baidu |
| `/api/tools/web-fetch` | POST | Fetch and extract text from URL |
| `/api/tools/agent-run` | POST | Run autonomous research task |

---

## 12. Data Flow

### Chat Flow

```
User Input → FastAPI Route → Provider.chat_stream()
    → SSE tokens → Browser renders markdown
```

### Pipeline Flow

```
Paper Text → StageAgent.call() → Provider.chat_with_retry()
    → LLM Response → extract_mermaid() → StageResult
    → Next stage → ... → Final Report
```

### OCR Flow

```
File Upload → BaiduOCR._submit_document() → Poll _poll_task()
    → Download markdown_url → Return text
```

### Agent Runner Flow

```
Task → LLM Reasoning Loop → Tool Calls → Results
    → LLM Synthesis → Final Answer
```

---

## 13. Security Considerations

### Current

- API keys stored in `settings.json` (local only)
- Environment variables for production secrets
- `.env` in `.gitignore`
- Sandboxed Python execution in agent runner

### Recommended for Production

- Add JWT/API key authentication to web API
- Implement CORS restrictions
- Add rate limiting
- Use HTTPS
- Add input validation on all endpoints
- Run in Docker with non-root user

---

## 14. Performance Characteristics

### Pipeline Execution

| Stage | Typical Latency | Token Usage |
|-------|----------------|-------------|
| Paper Analysis | 10-30s | ~2000 tokens |
| SRS Generation | 15-40s | ~3000 tokens |
| Module Design | 10-30s | ~2500 tokens |
| User Flow | 10-25s | ~2000 tokens |
| SDLC Plan | 10-25s | ~2000 tokens |
| Code Generation | 20-60s | ~4000 tokens |
| Debug Review | 10-30s | ~2000 tokens |
| Deployment | 10-30s | ~2000 tokens |
| Final Review | 10-25s | ~2000 tokens |
| **Total** | **2-5 minutes** | **~22,000 tokens** |

### Dev Mode

| Operation | Latency |
|-----------|---------|
| Full pipeline (9 stages) | < 1 second |
| Chat response | < 100ms |
| Streaming (3-word chunks) | 50ms per chunk |

---

## 15. Extension Points

### Adding a New Provider

1. Create a class inheriting from `LLMProvider` or `OpenAICompatibleProvider`
2. Implement `chat()`, `chat_stream()`, `list_models()`
3. Add to `PROVIDER_REGISTRY` in `providers.py`
4. Add to `__init__.py` exports

### Adding a New Pipeline Stage

1. Create a class inheriting from `StageAgent`
2. Implement `run()` that returns a `StageResult`
3. Add to `CollabuildPipeline.__init__()` stages dict
4. Add execution logic in `CollabuildPipeline.run()`

### Adding a New Tool to Agent Runner

1. Add tool name to `SYSTEM_PROMPT` in `AgentRunner`
2. Implement `_tool_<name>()` method
3. Add routing in `_execute_tool()`
4. Update `status()` tools list

### Adding a New Web Page

1. Create template in `web/templates/`
2. Add route in `web/app.py`
3. Add navigation link in `base.html` sidebar
