# Collabuild MAS v0.3

Multi-Agent System with a KoboldCPP-style web UI. Chat with AI models running locally or via cloud APIs — OpenRouter, NVIDIA Build, Anthropic Claude, Ollama, KoboldCPP, text-generation-webui, and any OpenAI-compatible endpoint. Includes a 9-stage research paper to production pipeline with full dev fallback for offline testing.

**Author:** [Sai Karun Nandipati](https://karun99.github.io)

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Browser (Web UI)                      │
│  ┌──────────┐  ┌─────────────────────────────────────┐  │
│  │ Sidebar   │  │         Chat Area                   │  │
│  │ Provider  │  │  ┌─────────────────────────────┐   │  │
│  │ Model     │  │  │  Messages (streamed)         │   │  │
│  │ Params    │  │  └─────────────────────────────┘   │  │
│  │ GGUF scan │  │  ┌─────────────────────────────┐   │  │
│  │ Nav       │  │  │  Input bar                   │   │  │
│  └──────────┘  │  └─────────────────────────────┘   │  │
│                 └─────────────────────────────────────┘  │
└───────────────────────┬─────────────────────────────────┘
                        │ SSE / JSON API
┌───────────────────────▼─────────────────────────────────┐
│              FastAPI Backend (app.py)                    │
│  /api/chat (SSE)  /api/settings  /api/models            │
│  /api/local-models  /api/providers/status                │
│  /api/pipeline/*  /api/chat/sync                         │
└──────┬────────────┬────────────┬────────────┬───────────┘
       │            │            │            │
┌──────▼──┐ ┌──────▼──┐ ┌──────▼──┐ ┌──────▼──┐
│OpenRouter│ │ NVIDIA  │ │ Ollama  │ │KoboldCPP│  ...
│  (cloud) │ │  Build  │ │ (local) │ │ (local) │
└──────────┘ └─────────┘ └─────────┘ └─────────┘
```

---

## Installation

### From PyPI (when published)

```bash
pip install collabuild-mas[web]
```

### From source

```bash
git clone https://github.com/collabuild-mas/collabuild-mas.git
cd collabuild-mas
pip install -e ".[web]"
```

### Dependencies

**Core:**
- `requests>=2.28` — HTTP client for API calls
- `pyyaml>=6.0` — Configuration loading

**Web (optional):**
- `fastapi>=0.110` — Web framework
- `uvicorn>=0.27` — ASGI server
- `jinja2>=3.1` — HTML templating
- `python-multipart>=0.0.9` — Form handling
- `sse-starlette>=2.0` — Server-Sent Events

---

## Quick Start

### 1. Launch the Web UI

```bash
collabuild web                    # default: http://127.0.0.1:8080
collabuild web --port 3000        # custom port
collabuild web --host 0.0.0.0     # bind all interfaces
collabuild web --reload           # auto-reload on code changes
```

### 2. Open in Browser

Navigate to `http://127.0.0.1:8080`

### 3. Configure a Provider

In the sidebar, select a provider and enter your settings:

| Provider | What you need |
|----------|--------------|
| **OpenRouter** | API key from [openrouter.ai](https://openrouter.ai) |
| **NVIDIA Build** | API key from [build.nvidia.com](https://build.nvidia.com) |
| **Ollama** | Run `ollama serve` locally (auto-detected) |
| **KoboldCPP** | Run KoboldCPP server locally (port 5001) |
| **text-gen-webui** | Run oobabooga locally (port 5000) |
| **Custom** | Any OpenAI-compatible `/v1/chat/completions` endpoint |

### 4. Start Chatting

Select a model and type your message. Responses stream in real-time.

---

## Supported Providers

### OpenRouter

Cloud API with 200+ models. Free tier available.

- **Endpoint:** `https://openrouter.ai/api/v1`
- **Auth:** API key (`OPENROUTER_API_KEY` env var)
- **Models:** Auto-fetched from API (gpt-4o, claude-3.5, llama-3.1, mixtral, gemma, etc.)
- **Streaming:** Full SSE support

### NVIDIA Build

Cloud API with 160+ open models from NVIDIA.

- **Endpoint:** `https://integrate.api.nvidia.com/v1`
- **Auth:** API key (`NVIDIA_API_KEY` env var)
- **Models:** Llama 3.1, Nemotron, Mixtral, Gemma, CodeLlama, Phi-3, StarCoder, etc.
- **Streaming:** Full SSE support

### Ollama

Local LLM inference server.

- **Endpoint:** `http://localhost:11434`
- **Auth:** None
- **Setup:**
  ```bash
  # Install Ollama
  curl -fsSL https://ollama.com/install.sh | sh

  # Pull a model
  ollama pull llama3.1
  ollama pull codellama
  ollama pull mistral

  # Start server (usually auto-starts)
  ollama serve
  ```
- **Streaming:** Native streaming support
- **Model list:** Auto-fetched from `/api/tags`

### KoboldCPP

Local GGUF model runner.

- **Endpoint:** `http://localhost:5001`
- **Auth:** None
- **Setup:**
  ```bash
  # Download koboldcpp
  # https://github.com/LostRuins/koboldcpp

  # Run with a GGUF model
  ./koboldcpp --model ~/models/llama-3.1-8b-instruct.Q4_K_M.gguf --port 5001
  ```
- **Streaming:** Supported via `/api/v1/generate` with `stream: true`
- **Model list:** Returns the currently loaded model

### text-generation-webui (oobabooga)

Local LLM server with OpenAI-compatible API.

- **Endpoint:** `http://localhost:5000`
- **Auth:** None
- **Setup:**
  ```bash
  # https://github.com/oobabooga/text-generation-webui
  # Start with --api flag
  python server.py --api --listen --port 5000
  ```
- **Streaming:** Full SSE via `/v1/chat/completions`
- **Model list:** Auto-fetched from `/v1/models`

### Custom API

Any endpoint implementing the OpenAI `/v1/chat/completions` spec works.

- Set the endpoint URL and API key in settings
- Used for: vLLM, llama.cpp server, LocalAI, LM Studio, etc.

---

## Local Model Discovery (.gguf / .ggml)

The app scans these directories for local model files:

```
~/models
~/Downloads
~/.cache/huggingface/hub
/opt/models
/usr/share/models
./models
```

Customizable in **Settings → Local Model Search Paths**.

Model files appear in the sidebar with format badge (GGUF/GGML) and file size. Click to select.

---

## Web UI Pages

### Chat (`/`)

The main interface. KoboldCPP-style layout with:

- **Sidebar:** Provider selector, model picker, local model browser, parameter sliders, system prompt, navigation
- **Chat area:** Streaming message display with markdown rendering, code blocks, user/AI avatars
- **Input bar:** Auto-resizing textarea, send/stop buttons, Enter to send, Shift+Enter for newline
- **Top bar:** Active provider badge, model label, clear/export buttons

**Features:**
- Real-time streaming via Server-Sent Events (SSE)
- Stop generation mid-response
- Export chat to Markdown
- Markdown rendering (code blocks, bold, italic, inline code)
- Mobile-responsive (sidebar collapses to hamburger menu)

### Settings (`/settings`)

Full configuration page:

- **Provider Configuration:** Select provider, set endpoint/API key/default model
- **Chat Defaults:** System prompt, temperature, max tokens, top_p, top_k, repeat penalty, context length
- **Local Model Search Paths:** Editable list of directories to scan
- **Provider Status:** Online/offline check for local providers
- **Provider Reference:** Table with endpoints, auth types, model counts

### Pipeline (`/pipeline`)

The 9-stage research paper → production pipeline:

1. **Paper Analysis** — Extract methodology, algorithms, architecture
2. **SRS Generation** — IEEE 830 Software Requirements Specification
3. **Module Design** — Module decomposition with interfaces
4. **User Flow Design** — UX flows with sequence diagrams
5. **SDLC Plan** — Sprint breakdown, milestones, timeline
6. **Code Generation** — Production-ready implementation code
7. **Debugging & Review** — Bug/security/performance review
8. **Deployment Plan** — Infrastructure, CI/CD, monitoring
9. **Final Review** — QA validation

Input a research paper text, select provider/model, and run. Progress streams in real-time with stage-by-stage updates.

---

## API Reference

### Chat

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat` | POST | Streaming chat (SSE) |
| `/api/chat/sync` | POST | Non-streaming chat |

**Request body:**
```json
{
  "messages": [{"role": "user", "content": "Hello"}],
  "model": "llama3.1",
  "provider": "ollama",
  "temperature": 0.7,
  "max_tokens": 4096,
  "system_prompt": "You are helpful."
}
```

**SSE response events:**
- `event: token` / `data: <token>` — Each generated token
- `event: done` / `data: ` — Generation complete
- `event: error` / `data: <error message>`

### Settings

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/settings` | GET | Get current settings |
| `/api/settings` | POST | Save settings (JSON body) |

### Models

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/models?provider=X` | GET | List available models from provider |
| `/api/local-models` | GET | Scan filesystem for .gguf/.ggml files |

### Provider Status

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/providers/status` | GET | Check which local providers are online |

### Pipeline

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/pipeline/run` | POST | Start a pipeline run |
| `/api/pipeline/{run_id}` | GET | Get run status/results |
| `/api/pipeline/{run_id}/stream` | GET | SSE stream of progress |

---

## Configuration

### config.yaml

Located at the project root. Defines provider defaults and pipeline settings.

```yaml
providers:
  openrouter:
    endpoint: "https://openrouter.ai/api/v1"
    api_key: "${OPENROUTER_API_KEY}"    # env var resolution
    model: "openrouter/free"

  nvidia:
    endpoint: "https://integrate.api.nvidia.com/v1"
    api_key: "${NVIDIA_API_KEY}"
    model: "nvidia/llama-3.1-nemotron-70b-instruct"

  ollama:
    endpoint: "http://localhost:11434"
    model: "llama3.1"

  koboldcpp:
    endpoint: "http://localhost:5001"
    model: "default"

  textgen:
    endpoint: "http://localhost:5000"
    model: "local"

  custom:
    endpoint: ""
    api_key: ""
    model: ""

model_search_paths:
  - "~/models"
  - "~/Downloads"
  - "~/.cache/huggingface/hub"
  - "/opt/models"

chat:
  system_prompt: "You are a helpful assistant."
  max_tokens: 4096
  temperature: 0.7
  top_p: 0.9
  top_k: 40
  repeat_penalty: 1.1
  context_length: 8192

pipeline:
  provider: "openrouter"
  stages:
    paper_analysis:
      agent: "Paper-Analyzer"
      temperature: 0.3
    # ... (9 stages)
```

### Environment Variables

| Variable | Provider | Description |
|----------|----------|-------------|
| `OPENROUTER_API_KEY` | OpenRouter | API key |
| `NVIDIA_API_KEY` | NVIDIA Build | API key |

### User Settings (persisted)

Saved to `collabuild/web/settings.json` when you click Save in the UI.

---

## CLI Usage

```bash
# Web UI (default)
collabuild web

# Pipeline via CLI
collabuild --provider ollama --model llama3.1 --paper "My paper text..."
collabuild --provider nvidia --model nvidia/llama-3.1-nemotron-70b-instruct --paper-file paper.txt
collabuild --provider koboldcpp --output report.md

# All flags
collabuild --provider {openrouter,nvidia,ollama,koboldcpp,textgen}
collabuild --model <model-name>
collabuild --api-key <key>
collabuild --endpoint <url>
collabuild --paper <text>
collabuild --paper-file <path>
collabuild --output <path>
collabuild --config <config.yaml>
```

---

## File Structure

```
collabuild/
├── __init__.py          # Package exports (v0.3.0)
├── __main__.py          # CLI entry point (collabuild command)
├── config.py            # YAML config loader with env var resolution
├── config.yaml          # Bundled default configuration
├── providers.py         # LLM providers (OpenRouter, NVIDIA, Claude, Ollama, KoboldCPP, textgen)
├── mas.py               # Multi-Agent System framework (Agent, Crew, Task, OCRAgent)
├── pipeline.py          # 9-stage research paper → production pipeline
├── ocr/
│   ├── __init__.py
│   └── baidu_ocr.py     # Baidu OCR — Unlimited document parsing + general OCR
├── research/
│   ├── __init__.py
│   ├── web_fetcher.py   # Enhanced web data fetcher (stdlib-only, no deps)
│   └── agent_runner.py  # Autonomous research agent with tool use
└── web/
    ├── __init__.py
    ├── app.py           # FastAPI app (routes, chat API, settings API, tools API)
    ├── settings.json    # Persisted user settings (auto-created)
    └── templates/
        ├── base.html    # Base template (Tokyo Night theme, shared CSS)
        ├── chat.html    # Main chat interface (KoboldCPP-style)
        ├── settings.html # Full settings page
        ├── pipeline.html # Pipeline runner page
        ├── tools.html   # Research tools page (OCR, web fetcher, agent)
        ├── index.html   # Redirect to /
        ├── running.html  # Redirect to /pipeline
        └── report.html   # Redirect to /pipeline
```

---

## Providers.py — Class Hierarchy

```
LLMProvider (ABC)
├── OpenAICompatibleProvider
│   ├── OpenRouterProvider      (openrouter.ai)
│   ├── NvidiaProvider          (integrate.api.nvidia.com)
│   └── TextGenWebUIProvider    (localhost:5000)
├── ClaudeProvider              (api.anthropic.com)
├── OllamaProvider              (localhost:11434)
└── KoboldCPPProvider           (localhost:5001)
```

Each provider implements:
- `chat()` — Non-streaming completion
- `chat_stream()` — Token-by-token streaming generator
- `list_models()` — Fetch available model names

---

## Theming

The UI uses a **Tokyo Night** color scheme (dark theme):

| Token | Color | Usage |
|-------|-------|-------|
| `--bg-primary` | `#1a1b26` | Main background |
| `--bg-secondary` | `#16161e` | Sidebar, header |
| `--bg-tertiary` | `#24283b` | Cards, inputs |
| `--accent-blue` | `#7aa2f7` | Primary actions |
| `--accent-green` | `#9ece6a` | Success, online |
| `--accent-red` | `#f7768e` | Errors, stop |
| `--accent-yellow` | `#e0af68` | KoboldCPP, warnings |
| `--accent-magenta` | `#bb9af7` | text-gen-webui |
| `--text-primary` | `#c0caf5` | Body text |
| `--text-muted` | `#565f89` | Labels, hints |

---

## Development

```bash
# Install dev dependencies
pip install -e ".[web,dev]"

# Run with auto-reload
collabuild web --reload

# Run in dev mode (offline, no API key needed)
collabuild --dev

# Run web UI in dev mode
collabuild web --dev

# Run tests
pytest

# Lint
ruff check collabuild/
```

### Dev Fallback Mechanism

Collabuild MAS includes a built-in `DevProvider` that returns structured mock responses for each pipeline stage without requiring any API key or network access. This ensures the code developed is clear, authentic, and implementable by providing verifiable reference outputs.

```bash
# Run the full 9-stage pipeline offline
collabuild --dev

# The pipeline will:
# 1. Analyze the sample paper (with Mermaid diagrams)
# 2. Generate SRS document (IEEE 830 format)
# 3. Design module architecture (class diagrams)
# 4. Design user flows (sequence diagrams)
# 5. Create SDLC plan (Gantt chart)
# 6. Generate production-ready code
# 7. Debug and review code
# 8. Plan deployment infrastructure
# 9. Perform final QA review
```

The DevProvider is activated via:
- CLI: `collabuild --dev`
- Config: `pipeline.provider: "dev"`
- Code: `create_provider({"provider": "dev"})`

---

## Deployment

### Docker (Recommended)

```bash
# Build the image
docker build -t collabuild-mas .

# Run with docker-compose
docker compose up -d

# Or run standalone
docker run -p 8080:8080 \
  -e OPENROUTER_API_KEY=sk-or-... \
  collabuild-mas
```

### Docker Compose

```yaml
# docker-compose.yml is included in the repo
# Set your API keys in .env file (copy from .env.example)
cp .env.example .env
# Edit .env with your API keys
docker compose up -d
```

### GitHub Actions CI/CD

The repository includes a GitHub Actions workflow (`.github/workflows/ci.yml`) that:
- Runs tests on Python 3.10-3.13
- Lints with ruff
- Builds the wheel and sdist
- Publishes to PyPI on version tags

```bash
# To publish a release
git tag v0.3.0
git push origin v0.3.0
# GitHub Actions will build and publish to PyPI
```

### Manual Deployment

```bash
# Install from the built wheel
pip install dist/collabuild_mas-0.3.0-py3-none-any.whl

# Or install from source
pip install -e ".[web]"

# Run
collabuild web --host 0.0.0.0 --port 8080
```

---

## Author

**Sai Karun Nandipati**
- Website: [https://karun99.github.io](https://karun99.github.io)
- GitHub: [https://github.com/collabuild-mas](https://github.com/collabuild-mas)

---

## License

MIT License — see [LICENSE](LICENSE) for details.
