"""LLM providers for Collabuild MAS — OpenRouter, NVIDIA Build, Ollama, KoboldCPP, text-generation-webui."""

import glob
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from collections.abc import Iterator

log = logging.getLogger("providers")

def messages_to_prompt(messages: list) -> str:
    """Convert chat messages to a plain text prompt for non-chat APIs (KoboldCPP etc.)."""
    prompt = ""
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "system":
            prompt += f"System: {content}\n"
        elif role == "user":
            prompt += f"User: {content}\n"
        elif role == "assistant":
            prompt += f"Assistant: {content}\n"
    prompt += "Assistant: "
    return prompt


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    def __init__(self, name: str = "default"):
        self.name = name

    @abstractmethod
    def chat(self, model: str, messages: list, temperature: float = 0.3, max_tokens: int = 4096) -> str:
        ...

    def chat_stream(self, model: str, messages: list, temperature: float = 0.3,
                    max_tokens: int = 4096) -> Iterator[str]:
        """Streaming chat — yields token strings. Default falls back to non-streaming."""
        yield self.chat(model, messages, temperature, max_tokens)

    def list_models(self) -> list:
        """Return available model names. Override in subclasses."""
        return []

    def chat_with_retry(self, model: str, messages: list, temperature: float = 0.3,
                        max_tokens: int = 4096, retries: int = 3) -> str:
        for attempt in range(retries):
            try:
                return self.chat(model, messages, temperature, max_tokens)
            except Exception as e:
                log.warning(f"[{self.name}] attempt {attempt+1}/{retries} failed: {e}")
                if attempt == retries - 1:
                    raise
                time.sleep(2 ** attempt)


# ═══════════════════════════════════════════════════════════════
# OpenAI-compatible base (used by OpenRouter, NVIDIA Build, textgen)
# ═══════════════════════════════════════════════════════════════

class OpenAICompatibleProvider(LLMProvider):
    """Base for any OpenAI-compatible /v1/chat/completions endpoint."""
    def __init__(self, api_key: str = "", endpoint: str = "", name: str = "openai-compat",
                 extra_headers: dict = None):
        super().__init__(name)
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.extra_headers = extra_headers or {}

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json", **self.extra_headers}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def chat(self, model: str, messages: list, temperature: float = 0.3, max_tokens: int = 4096) -> str:
        import requests
        url = f"{self.endpoint}/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        r = requests.post(url, json=payload, headers=self._headers(), timeout=120)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    def chat_stream(self, model: str, messages: list, temperature: float = 0.3,
                    max_tokens: int = 4096) -> Iterator[str]:
        import requests
        url = f"{self.endpoint}/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        with requests.post(url, json=payload, headers=self._headers(), timeout=120, stream=True) as r:
            r.raise_for_status()
            for line in r.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue
                data = line[6:]
                if data.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    delta = chunk["choices"][0].get("delta", {})
                    if "content" in delta:
                        yield delta["content"]
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

    def list_models(self) -> list:
        import requests
        try:
            r = requests.get(f"{self.endpoint}/models", headers=self._headers(), timeout=10)
            r.raise_for_status()
            data = r.json()
            models = data.get("data", [])
            return [m.get("id", "") for m in models if m.get("id")]
        except Exception as e:
            log.warning(f"[{self.name}] list_models failed: {e}")
            return []


# ═══════════════════════════════════════════════════════════════
# Concrete providers
# ═══════════════════════════════════════════════════════════════

class OpenRouterProvider(OpenAICompatibleProvider):
    """OpenRouter — 200+ models, free tier."""
    def __init__(self, api_key: str = "", endpoint: str = "https://openrouter.ai/api/v1",
                 name: str = "openrouter"):
        super().__init__(api_key=api_key, endpoint=endpoint, name=name,
                         extra_headers={"HTTP-Referer": "https://github.com/collabuild-mas", "X-Title": "Collabuild MAS"})
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")


class NvidiaProvider(OpenAICompatibleProvider):
    """NVIDIA Build (build.nvidia.com) — 160+ open models via API."""
    def __init__(self, api_key: str = "", endpoint: str = "https://integrate.api.nvidia.com/v1",
                 name: str = "nvidia"):
        super().__init__(api_key=api_key, endpoint=endpoint, name=name)
        self.api_key = api_key or os.getenv("NVIDIA_API_KEY", "")


class OllamaProvider(LLMProvider):
    """Ollama local LLM server."""
    def __init__(self, endpoint: str = "http://localhost:11434", name: str = "ollama"):
        super().__init__(name)
        self.endpoint = endpoint.rstrip("/")

    def chat(self, model: str, messages: list, temperature: float = 0.3, max_tokens: int = 4096) -> str:
        import requests
        url = f"{self.endpoint}/api/chat"
        payload = {
            "model": model,
            "messages": messages,
            "options": {"temperature": temperature, "num_predict": max_tokens},
            "stream": False,
        }
        r = requests.post(url, json=payload, timeout=300)
        r.raise_for_status()
        return r.json()["message"]["content"]

    def chat_stream(self, model: str, messages: list, temperature: float = 0.3,
                    max_tokens: int = 4096) -> Iterator[str]:
        import requests
        url = f"{self.endpoint}/api/chat"
        payload = {
            "model": model,
            "messages": messages,
            "options": {"temperature": temperature, "num_predict": max_tokens},
            "stream": True,
        }
        with requests.post(url, json=payload, timeout=300, stream=True) as r:
            r.raise_for_status()
            for line in r.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    if "message" in chunk and "content" in chunk["message"]:
                        yield chunk["message"]["content"]
                except json.JSONDecodeError:
                    continue

    def list_models(self) -> list:
        import requests
        try:
            r = requests.get(f"{self.endpoint}/api/tags", timeout=10)
            r.raise_for_status()
            data = r.json()
            return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            log.warning(f"[ollama] list_models failed: {e}")
            return []


class KoboldCPPProvider(LLMProvider):
    """KoboldCPP local GGUF runner."""
    def __init__(self, endpoint: str = "http://localhost:5001", name: str = "koboldcpp"):
        super().__init__(name)
        self.endpoint = endpoint.rstrip("/")

    def chat(self, model: str, messages: list, temperature: float = 0.3, max_tokens: int = 4096) -> str:
        import requests
        url = f"{self.endpoint}/api/v1/generate"
        prompt = messages_to_prompt(messages)
        context_len = min(len(prompt) + max_tokens * 4, 8192)
        payload = {
            "prompt": prompt,
            "max_context_length": context_len,
            "max_length": max_tokens,
            "temperature": temperature,
            "top_p": 0.9,
            "top_k": 40,
            "rep_pen": 1.1,
        }
        r = requests.post(url, json=payload, timeout=300)
        r.raise_for_status()
        data = r.json()
        return data.get("results", [{}])[0].get("text", "")

    def chat_stream(self, model: str, messages: list, temperature: float = 0.3,
                    max_tokens: int = 4096) -> Iterator[str]:
        import requests
        url = f"{self.endpoint}/api/v1/generate"
        prompt = messages_to_prompt(messages)
        context_len = min(len(prompt) + max_tokens * 4, 8192)
        payload = {
            "prompt": prompt,
            "max_context_length": context_len,
            "max_length": max_tokens,
            "temperature": temperature,
            "top_p": 0.9,
            "top_k": 40,
            "rep_pen": 1.1,
            "stream": True,
        }
        with requests.post(url, json=payload, timeout=300, stream=True) as r:
            r.raise_for_status()
            for line in r.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    if "token" in chunk:
                        yield chunk["token"]
                    elif "results" in chunk and chunk["results"]:
                        text = chunk["results"][0].get("text", "")
                        if text:
                            yield text
                except json.JSONDecodeError:
                    continue

    def list_models(self) -> list:
        import requests
        try:
            r = requests.get(f"{self.endpoint}/model", timeout=10)
            r.raise_for_status()
            data = r.json()
            model_id = data.get("result", "")
            return [model_id] if model_id else []
        except Exception as e:
            log.warning(f"[koboldcpp] list_models failed: {e}")
            return []


class ClaudeProvider(LLMProvider):
    """Anthropic Claude via Messages API (api.anthropic.com).

    Uses direct HTTP — no SDK dependency. Supports streaming via SSE.
    Models: claude-opus-4-8, claude-sonnet-4-20250514, claude-haiku-4-5-20251001, etc.
    """
    DEFAULT_ENDPOINT = "https://api.anthropic.com/v1"
    DEFAULT_VERSION = "2023-06-01"

    def __init__(self, api_key: str = "", endpoint: str = "", name: str = "claude",
                 model: str = ""):
        super().__init__(name)
        self.endpoint = (endpoint or self.DEFAULT_ENDPOINT).rstrip("/")
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.model = model or os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

    def _headers(self) -> dict:
        h = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": self.DEFAULT_VERSION,
        }
        return h

    def chat(self, model: str, messages: list, temperature: float = 0.3,
             max_tokens: int = 4096) -> str:
        import requests
        model = model or self.model
        # Separate system messages from conversation
        system_text = ""
        conv_msgs = []
        for m in messages:
            if m.get("role") == "system":
                system_text += m.get("content", "") + "\n"
            else:
                conv_msgs.append({"role": m.get("role", "user"), "content": m.get("content", "")})
        if not conv_msgs:
            conv_msgs = [{"role": "user", "content": "Hello"}]

        payload = {
            "model": model,
            "messages": conv_msgs,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_text.strip():
            payload["system"] = system_text.strip()

        r = requests.post(f"{self.endpoint}/messages", json=payload,
                          headers=self._headers(), timeout=300)
        r.raise_for_status()
        data = r.json()
        content = data.get("content", [])
        return content[0].get("text", "") if content else ""

    def chat_stream(self, model: str, messages: list, temperature: float = 0.3,
                    max_tokens: int = 4096) -> Iterator[str]:
        import requests
        model = model or self.model
        system_text = ""
        conv_msgs = []
        for m in messages:
            if m.get("role") == "system":
                system_text += m.get("content", "") + "\n"
            else:
                conv_msgs.append({"role": m.get("role", "user"), "content": m.get("content", "")})
        if not conv_msgs:
            conv_msgs = [{"role": "user", "content": "Hello"}]

        payload = {
            "model": model,
            "messages": conv_msgs,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        if system_text.strip():
            payload["system"] = system_text.strip()

        with requests.post(f"{self.endpoint}/messages", json=payload,
                           headers=self._headers(), timeout=300, stream=True) as r:
            r.raise_for_status()
            for line in r.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    evt = json.loads(data_str)
                    evt_type = evt.get("type", "")
                    if evt_type == "content_block_delta":
                        delta = evt.get("delta", {})
                        if delta.get("type") == "text_delta":
                            yield delta.get("text", "")
                except (json.JSONDecodeError, KeyError):
                    continue

    def list_models(self) -> list:
        """Claude models — static list since Anthropic doesn't have a models endpoint."""
        return [
            "claude-opus-4-8",
            "claude-sonnet-4-20250514",
            "claude-haiku-4-5-20251001",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
            "claude-3-haiku-20240307",
        ]


class TextGenWebUIProvider(OpenAICompatibleProvider):
    """text-generation-webui (oobabooga) via OpenAI-compatible API."""
    def __init__(self, endpoint: str = "http://localhost:5000", name: str = "textgen", **kwargs):
        super().__init__(api_key=kwargs.get("api_key", ""), endpoint=endpoint, name=name)


# ═══════════════════════════════════════════════════════════════
# Dev fallback — offline mock provider for pipeline testing
# ═══════════════════════════════════════════════════════════════

class DevProvider(LLMProvider):
    """Offline mock provider for development, testing, and demo.

    Returns structured, realistic responses for each pipeline stage without
    requiring any API key or network access. Ensures the code developed is
    clear, authentic, and implementable by providing verifiable reference
    outputs at every stage.

    Activated via:
        - CLI:    collabuild --dev
        - Config: pipeline.provider: "dev"
        - Code:   create_provider({"provider": "dev"})
    """

    STAGE_RESPONSES = {
        "paper analysis": """## Paper Analysis

### 1. TITLE & AUTHORS
**Unlimited OCR Works: Welcome the Era of One-shot Long-horizon Parsing**
Youyang Yin, Huanhuan Liu, et al. — Baidu Inc.

### 2. PROBLEM STATEMENT
Traditional OCR systems process documents page-by-page or in chunks, losing cross-page context and introducing alignment errors. Long-form documents (50+ pages) require a unified parsing approach.

### 3. KEY METHODOLOGY
1. Vision Encoder (ViT-L/14) processes document images at variable resolutions
2. Language Decoder (Qwen2.5-7B) generates structured text output
3. Adaptive cropping handles arbitrary document length via overlapping tiles
4. No-repeat n-gram processor prevents repetition across full 32K context

### 4. ALGORITHMS USED
- Vision-Language Model with cross-attention fusion
- Adaptive tile-based cropping with overlap preservation
- No-repeat n-gram logit processing for controlled generation

### 5. ARCHITECTURE
- Input → ViT-L/14 Encoder → Cross-Attention → Qwen2.5-7B Decoder → Structured Output
- Two inference modes: 'gundam' (single-page detailed) and 'base' (multi-page)

### 6. DATASETS & METRICS
- Synthetic pre-training on PDF-to-image pipelines
- Fine-tuned on invoices, receipts, papers, forms, books
- Character Error Rate (CER) reduced by 40% vs prior methods

### 7. TECH STACK IMPLIED
- HuggingFace Transformers, vLLM, SGLang inference backends
- Python, PyTorch, CUDA
- ViT-L/14 + Qwen2.5-7B architecture

### 8. LIMITATIONS
- 32K context window limits ultra-long documents
- Requires GPU for reasonable throughput
- Bilingual (EN/ZH) optimization may not transfer to all languages

### 9. REPRODUCIBILITY
- Open-source under MIT license on HuggingFace and ModelScope
- Two-stage training pipeline documented

```mermaid
flowchart TD
    A[Input Document] --> B{Crop Mode?}
    B -->|gundam| C[Single-page 640px crop]
    B -->|base| D[Multi-page 1024px tiles]
    C --> E[ViT-L/14 Encoder]
    D --> E
    E --> F[Cross-Attention Fusion]
    F --> G[Qwen2.5-7B Decoder]
    G --> H{No-Repeat Check}
    H -->|clean| I[Structured Output]
    H -->|repeat detected| J[Logit Processing]
    J --> G
```""",

        "srs generation": """## Software Requirements Specification (IEEE 830)

### 1. INTRODUCTION
**Purpose:** Build a production document parsing system based on Unlimited-OCR.
**Scope:** End-to-end document-to-Markdown pipeline with web interface.

### 2. OVERALL DESCRIPTION
- **Product Perspective:** Standalone web service with REST API
- **User Characteristics:** Developers, data engineers, document processing teams
- **Constraints:** GPU required for inference, 32K token context limit

### 3. SPECIFIC REQUIREMENTS

#### Functional
- FR-1: Upload documents (PDF, DOC, images) via web UI or API
- FR-2: Parse documents to Markdown with layout preservation
- FR-3: Support batch processing of multiple documents
- FR-4: Export parsed results in Markdown, JSON, or plain text

#### Non-Functional
- NF-1: Process single page in < 5 seconds on A100 GPU
- NF-2: Support documents up to 500 pages
- NF-3: 99.9% uptime for API endpoint
- NF-4: Handle 100 concurrent parsing requests

### 4. SYSTEM FEATURES
- Document Upload Module
- OCR Engine (Unlimited-OCR core)
- Result Formatter (Markdown/JSON export)
- Web Dashboard
- REST API Layer

### 5. EXTERNAL INTERFACES
- Web UI: HTML/CSS/JS single-page application
- REST API: JSON over HTTPS
- File System: Local or S3-compatible storage

### 6. DATA REQUIREMENTS
- Input: PDF, DOC, DOCX, PPT, images (JPG, PNG, BMP, TIFF)
- Output: Markdown text, JSON structured data
- Storage: Temporary file storage during processing

### 7. ASSUMPTIONS
- GPU infrastructure available (A100 or equivalent)
- Network access to HuggingFace for model download
- Python 3.10+ runtime

```mermaid
graph LR
    U[User] -->|Upload Document| API[REST API]
    API -->|Store| FS[File Storage]
    API -->|Queue| Q[Task Queue]
    Q -->|Process| OCR[OCR Engine]
    OCR -->|Parse| VLM[Vision-Language Model]
    VLM -->|Output| FMT[Formatter]
    FMT -->|Return| API
    API -->|Stream| U
```""",

        "module design": """## Module Architecture

### 1. HIGH-LEVEL ARCHITECTURE
```
┌─────────────────────────────────────────────┐
│              Web Layer (FastAPI)             │
│  Routes: /api/upload, /api/parse, /api/status│
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│           Service Layer                      │
│  DocumentService, ParseService, ExportService│
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│           Core Engine                        │
│  UnlimitedOCR, CropEngine, Decoder          │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│           Storage Layer                      │
│  FileStore, CacheManager, ResultDB          │
└─────────────────────────────────────────────┘
```

### 2. MODULE DECOMPOSITION

| Module | Responsibility | Inputs | Outputs |
|--------|---------------|--------|---------|
| `document_service` | Upload, validate, store files | HTTP multipart | Document ID |
| `parse_engine` | Run VLM inference on documents | Document path | Raw text |
| `crop_module` | Adaptive tile-based cropping | Image/Page | Cropped tiles |
| `format_service` | Convert raw output to Markdown/JSON | Raw text | Formatted doc |
| `export_service` | Package results for download | Formatted doc | File/URL |
| `cache_manager` | Cache parsed results | Doc hash | Cached result |
| `api_routes` | HTTP endpoint handlers | Request | Response |

### 3. MODULE INTERFACES
```python
class ParseEngine:
    def parse(self, document: Document) -> ParseResult: ...
    def parse_batch(self, docs: list[Document]) -> list[ParseResult]: ...

class CropModule:
    def crop_gundam(self, image: Image) -> list[Tile]: ...
    def crop_base(self, image: Image) -> list[Tile]: ...

class FormatService:
    def to_markdown(self, raw: str) -> str: ...
    def to_json(self, raw: str) -> dict: ...
```

### 4. DATA FLOW
Upload → Validate → Store → Queue → Crop → Encode → Decode → Format → Cache → Return

### 5. TECHNOLOGY RECOMMENDATIONS
- FastAPI (async web framework)
- PyTorch + HuggingFace Transformers (ML inference)
- Redis (task queue, caching)
- PostgreSQL (metadata, job tracking)
- MinIO/S3 (file storage)

```mermaid
classDiagram
    class DocumentService {
        +upload(file) DocumentID
        +validate(doc) bool
        +store(doc) Path
    }
    class ParseEngine {
        +parse(doc) ParseResult
        +parse_batch(docs) list
    }
    class CropModule {
        +crop_gundam(img) list
        +crop_base(img) list
    }
    class FormatService {
        +to_markdown(raw) str
        +to_json(raw) dict
    }
    class ExportService {
        +package(result) File
        +stream(result) Response
    }
    DocumentService --> ParseEngine
    ParseEngine --> CropModule
    ParseEngine --> FormatService
    FormatService --> ExportService
```""",

        "user flow design": """## User Flow Design

### 1. PRIMARY FLOW (Happy Path)
1. User opens web app → lands on Dashboard
2. Clicks "Upload Document" → file picker opens
3. Selects file → upload progress bar shows
4. Clicks "Parse" → processing indicator appears
5. Real-time progress: Crop → Encode → Decode → Format
6. Result displayed with Markdown preview
7. User clicks "Export" → downloads .md or .json

### 2. SECONDARY FLOWS
- **Batch Upload:** Select multiple files → queue processing → results tab
- **Re-parse:** Click "Re-process" on existing result with different settings
- **Compare:** Side-by-side view of original vs parsed output

### 3. ERROR FLOWS
- **Invalid file type:** Show error toast, return to upload
- **Parse failure:** Show error details, offer retry
- **Timeout:** Auto-retry once, then show manual retry button

### 4. USER DECISIONS
- Crop mode selection (gundam vs base)
- Output format (Markdown, JSON, plain text)
- Quality vs speed tradeoff

### 5. NAVIGATION MAP
```
Dashboard → Upload → Processing → Result → Export
    │                    │           │
    ├── Settings         ├── Status  ├── Re-parse
    ├── History          └── Cancel  └── Compare
    └── Help
```

```mermaid
sequenceDiagram
    actor User
    participant UI as Web App
    participant API as Backend
    participant OCR as OCR Engine
    participant VLM as VLM Model
    participant DB as Storage

    User->>UI: Upload Document
    UI->>API: POST /api/upload
    API->>DB: Store file
    API-->>UI: {document_id, status: "uploaded"}

    User->>UI: Click Parse
    UI->>API: POST /api/parse/{id}
    API->>OCR: process(document)
    OCR->>OCR: Adaptive Crop
    OCR->>VLM: encode(tiles)
    VLM-->>OCR: raw_text
    OCR->>OCR: No-repeat filter
    OCR-->>API: ParseResult
    API->>DB: Store result
    API-->>UI: SSE stream {progress, result}

    UI-->>User: Display parsed Markdown
    User->>UI: Export
    UI->>API: GET /api/export/{id}?format=md
    API-->>User: Download file
```""",

        "sdlc plan": """## SDLC Plan

### 1. PHASES
| Phase | Duration | Deliverables |
|-------|----------|-------------|
| Requirements | 1 week | SRS document, user stories |
| Design | 1 week | Architecture, API specs, UI mockups |
| Implementation | 4 weeks | Core engine, API, web UI |
| Testing | 2 weeks | Unit tests, integration tests, load tests |
| Deployment | 1 week | Docker images, CI/CD, monitoring |
| Maintenance | Ongoing | Bug fixes, model updates |

### 2. SPRINT BREAKDOWN (2-week sprints)

**Sprint 1:** Project setup, core OCR engine, basic API
**Sprint 2:** Crop module, VLM integration, batch processing
**Sprint 3:** Web UI, file upload, result display
**Sprint 4:** Export service, caching, performance optimization
**Sprint 5:** Testing, bug fixes, documentation
**Sprint 6:** Deployment, monitoring, launch prep

### 3. MILESTONES
- M1 (Week 2): Core engine parsing single pages
- M2 (Week 4): Full pipeline end-to-end
- M3 (Week 6): Web UI complete
- M4 (Week 8): Production-ready

### 4. RISK ASSESSMENT
| Risk | Impact | Mitigation |
|------|--------|-----------|
| GPU cost overrun | High | Use spot instances, implement caching |
| Model performance regression | High | A/B testing, rollback strategy |
| Scalability limits | Medium | Load testing, auto-scaling config |
| Security vulnerabilities | Medium | Regular audits, input validation |

```mermaid
gantt
    title Project Timeline
    dateFormat  YYYY-MM-DD
    axisFormat  %b %d

    section Requirements
    SRS & User Stories     :a1, 2026-01-01, 5d

    section Design
    Architecture           :b1, after a1, 3d
    API Spec               :b2, after b1, 2d
    UI Mockups             :b3, after a1, 5d

    section Implementation
    Core OCR Engine        :c1, after b2, 10d
    API Layer              :c2, after c1, 7d
    Web UI                 :c3, after c2, 10d
    Export & Cache         :c4, after c3, 5d

    section Testing
    Unit Tests             :d1, after c4, 5d
    Integration Tests      :d2, after d1, 5d
    Load Testing           :d3, after d2, 3d

    section Deployment
    Docker & CI/CD         :e1, after d3, 5d
    Monitoring             :e2, after e1, 2d
```""",

        "code generation": """## Code Generation

### File: src/core/parse_engine.py
```python
# Core document parsing engine using Unlimited-OCR architecture.

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import logging

log = logging.getLogger(__name__)

@dataclass
class ParseResult:
    text: str
    markdown: str
    page_count: int
    char_count: int
    confidence: float

class ParseEngine:
    def __init__(self, model_path: str, device: str = "cuda"):
        self.model_path = model_path
        self.device = device
        self._model = None

    def parse(self, document_path: Path) -> ParseResult:
        log.info("Parsing: %s", document_path.name)
        pages = self._load_document(document_path)
        tiles = self._crop_tiles(pages)
        raw_text = self._run_inference(tiles)
        markdown = self._format_markdown(raw_text)
        return ParseResult(
            text=raw_text, markdown=markdown,
            page_count=len(pages), char_count=len(raw_text),
            confidence=0.95,
        )

    def _load_document(self, path: Path) -> list:
        if path.suffix.lower() == ".pdf":
            return self._load_pdf(path)
        return self._load_image(path)

    def _crop_tiles(self, pages: list) -> list:
        tiles = []
        for page in pages:
            tiles.extend(self._adaptive_crop(page))
        return tiles

    def _run_inference(self, tiles: list) -> str:
        return "[Inference result]"

    def _format_markdown(self, raw: str) -> str:
        return raw
```

### File: src/api/routes.py
```python
# FastAPI routes for document parsing service.

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from pathlib import Path
import uuid, logging

log = logging.getLogger(__name__)
router = APIRouter()

@router.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    doc_id = uuid.uuid4().hex[:12]
    content = await file.read()
    path = Path(f"/tmp/docs/{doc_id}_{file.filename}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return {"document_id": doc_id, "filename": file.filename, "size": len(content)}

@router.post("/api/parse/{doc_id}")
async def parse_document(doc_id: str):
    from ..core.parse_engine import ParseEngine
    engine = ParseEngine(model_path="models/unlimited-ocr")
    path = list(Path("/tmp/docs").glob(f"{doc_id}_*"))
    if not path:
        raise HTTPException(404, "Document not found")
    result = engine.parse(path[0])
    return {"doc_id": doc_id, "markdown": result.markdown, "pages": result.page_count}
```""",

        "debugging & review": """## Code Review & Debugging

### 1. BUGS FOUND
| # | Severity | File | Description | Fix |
|---|----------|------|-------------|-----|
| 1 | CRITICAL | parse_engine.py | No input validation on file size | Add `if len(content) > MAX_SIZE: raise ValueError` |
| 2 | HIGH | routes.py | Path traversal possible via filename | Use `Path(filename).name` to strip directory components |
| 3 | MEDIUM | parse_engine.py | No timeout on inference calls | Add `timeout` parameter with default 300s |
| 4 | LOW | routes.py | Missing content-type validation | Add file extension whitelist |

### 2. SECURITY
- **Path traversal:** Sanitize filenames before storage (FIXED in #2)
- **Resource exhaustion:** Add max file size limit (FIXED in #1)
- **No auth:** Add API key or JWT authentication for production
- **CORS:** Restrict to known origins in production

### 3. PERFORMANCE
- **N+1 on batch:** Process tiles in parallel with `ThreadPoolExecutor`
- **Memory:** Stream large files instead of loading entirely into RAM
- **Cache:** Add Redis cache for repeated document hashes

### 4. CODE QUALITY
- Add type hints to all public methods
- Add docstrings to all classes
- Extract constants to config module
- Add structured logging with correlation IDs

### 5. TEST COVERAGE
- Unit: ParseEngine, CropModule, FormatService
- Integration: API routes with mock engine
- Load: 100 concurrent parse requests

### CORRECTED CODE
```python
# parse_engine.py — with fixes applied
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".ppt", ".jpg", ".png", ".bmp", ".tif"}
MAX_FILE_SIZE_MB = 100

def parse(self, document_path: Path) -> ParseResult:
    if document_path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {document_path.suffix}")
    if document_path.stat().st_size > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise ValueError(f"File exceeds {MAX_FILE_SIZE_MB}MB limit")
    # ... rest of implementation
```""",

        "deployment plan": """## Deployment Plan

### 1. INFRASTRUCTURE
- **Cloud:** AWS (primary), GCP (failover)
- **Region:** us-east-1 (primary), us-west-2 (DR)
- **GPU:** 2x A100 40GB instances for inference
- **CPU:** 4x c6i.xlarge for API + web serving

### 2. CONTAINERIZATION
```dockerfile
# Multi-stage build
FROM python:3.12-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM nvidia/cuda:12.2-runtime
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY . .
EXPOSE 8080
CMD ["collabuild", "web", "--host", "0.0.0.0", "--port", "8080"]
```

### 3. ORCHESTRATION
```yaml
# docker-compose.yml
services:
  api:
    build: .
    ports: ["8080:8080"]
    environment:
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - NVIDIA_API_KEY=${NVIDIA_API_KEY}
    deploy:
      replicas: 2
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
```

### 4. CI/CD
```yaml
# GitHub Actions
name: Deploy
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker build -t collabuild .
      - run: docker push ghcr.io/collabuild/collabuild:latest
      - run: kubectl apply -f k8s/
```

### 5. MONITORING
- Prometheus metrics: request latency, error rate, GPU utilization
- Grafana dashboards: system health, pipeline performance
- PagerDuty alerts: error rate > 5%, latency > 10s

### 6. COST ESTIMATE
| Component | Monthly Cost |
|-----------|-------------|
| 2x A100 instances | $4,500 |
| 4x API instances | $600 |
| Redis (ElastiCache) | $150 |
| S3 storage | $50 |
| CloudFront CDN | $100 |
| **Total** | **~$5,400** |

```mermaid
graph TB
    subgraph "CDN Layer"
        CF[CloudFront]
    end
    subgraph "Load Balancer"
        ALB[ALB]
    end
    subgraph "Compute"
        API1[API Instance 1]
        API2[API Instance 2]
        GPU1[GPU Instance 1]
        GPU2[GPU Instance 2]
    end
    subgraph "Data"
        REDIS[(Redis Cache)]
        S3[(S3 Storage)]
        DB[(PostgreSQL)]
    end
    User --> CF --> ALB
    ALB --> API1 & API2
    API1 & API2 --> GPU1 & GPU2
    API1 & API2 --> REDIS & S3 & DB
```""",

        "final review": """## Final Review

### 1. ACCURACY — PASS
All pipeline outputs correctly reflect the paper's methodology, algorithms, and architecture. The Unlimited-OCR pipeline stages (ViT-L/14 → Qwen2.5-7B → No-repeat filter) are accurately captured in all design documents.

### 2. COMPLETENESS — PASS
- SRS covers all functional and non-functional requirements from the paper
- Module design includes all 7 identified components
- User flows cover happy path, error paths, and edge cases
- Deployment plan addresses GPU requirements and scaling

### 3. EFFICIENCY — PASS
- Recommended tech stack (FastAPI + PyTorch + Redis) is performant
- Caching strategy reduces redundant GPU inference
- Batch processing with parallel tiles optimizes throughput

### 4. FEASIBILITY — PASS
- Can be built within 8-week timeline by a team of 3-4 engineers
- GPU costs are within typical startup budget (~$5,400/month)
- Open-source dependencies minimize licensing issues

### 5. REPRODUCIBILITY — PASS
- Code generation includes complete, runnable implementations
- Docker setup ensures consistent environments
- Documentation covers setup, configuration, and deployment

### 6. GAP ANALYSIS
| Gap | Severity | Recommendation |
|-----|----------|---------------|
| No authentication in API | HIGH | Add JWT/API key before production |
| No rate limiting | MEDIUM | Implement per-user rate limits |
| No monitoring in code | LOW | Add Prometheus metrics exporter |

**Overall Verdict: PASS** — Pipeline outputs are clear, authentic, and fully implementable. The system can be built from these specifications with high confidence in the result.""",

        "readme generation": """# Unlimited-OCR

An end-to-end document parsing engine that converts long-form, multi-page documents (PDFs, scans, invoices, books) into structured text in a single forward pass, without page-by-page chunking or lost cross-page context.

## Overview

Traditional OCR systems process documents page-by-page or in small chunks, which breaks layout continuity and drops accuracy on long documents. **Unlimited-OCR** solves this with a vision-language model (ViT-L/14 + Qwen2.5-7B) that reads an entire document in one pass over a 32K token context. Adaptive overlapping-tile cropping preserves layout across page boundaries, and a no-repeat n-gram constraint stops hallucinated repetition — reducing character error rate by 40% versus prior state-of-the-art while holding throughput.

## Key Features

- **One-shot Long-Horizon Parsing**: Single forward pass over arbitrarily long documents with no sequential page processing.
- **Adaptive Overlapping Cropping**: Splits documents into context-preserving tiles so structure survives page boundaries.
- **No-Repeat n-Gram Constraint**: Decoding-time token cache that suppresses hallucinated repetition in long outputs.
- **Custom Logit Processor**: Penalty and formatting rules applied to logits before sampling.
- **Two Inference Modes**: `gundam` (detailed single-page) and `base` (fast multi-page).
- **Multi-Backend Inference**: HuggingFace Transformers, vLLM, and SGLang.
- **Production-Ready**: Docker, CI/CD, REST API, and OpenRouter/NVIDIA/Ollama model support.

## Architecture

```
User
|
Application Layer
|
AI Processing Layer
|
Model Layer
|
Data / Infrastructure Layer
```

### Component Explanation

- **User**: Web UI or REST API client uploading documents and downloading parsed output.
- **Application Layer**: FastAPI service exposing upload, parse, status, and export endpoints.
- **AI Processing Layer**: Core engine orchestrating adaptive cropping, vision encoding, and decoding with the no-repeat constraint.
- **Model Layer**: ViT-L/14 vision encoder fused with the Qwen2.5-7B language decoder via cross-attention.
- **Data / Infrastructure Layer**: Object storage for documents, result cache, and GPU inference nodes.

## Technology Stack

- **Core Language**: Python 3.10+
- **API Framework**: FastAPI
- **Model / Inference**: PyTorch, HuggingFace Transformers, vLLM, SGLang
- **Vision Model**: ViT-L/14
- **Language Model**: Qwen2.5-7B (32K context)
- **Storage / Cache**: Redis, S3-compatible object storage
- **Containerization**: Docker, Docker Compose

## Installation

git clone https://github.com/example/unlimited-ocr.git
cd unlimited-ocr
pip install -r requirements.txt

### System Dependencies

For GPU inference:

sudo apt-get install -y nvidia-cuda-toolkit
ollama pull qwen2.5-7b

## Quick Start

from unlimited_ocr import OCRParser

parser = OCRParser(mode="base")          # or mode="gundam" for detailed pages
result = parser.parse("invoice.pdf")     # single forward pass
print(result.markdown)

## Configuration

Create a `.env` file in the root directory:

OPENROUTER_API_KEY=sk-or-...
MODEL_MODE=base
MAX_TOKENS=32768
BATCH_SIZE=4

### Configuration File (`config.yaml`)

ocr:
  mode: base          # gundam | base
  base_size: 1024
  image_size: 1024
  crop_mode: false

inference:
  backend: vllm       # transformers | vllm | sglang
  gpu: 1

## API Reference

### Parse a Document

```
POST /api/parse
```

**Payload:**

{
  "file": "invoice.pdf",
  "mode": "base"
}

**Response:**

{
  "document_id": "a1b2c3",
  "markdown": "# Invoice\\n\\n- Total: $1,200",
  "pages": 12,
  "cer": 0.021
}

### Get Job Status

```
GET /api/jobs/{id}
```

## Deployment

### Docker Compose

docker-compose -f docker-compose.yml up -d

### Kubernetes

kubectl apply -f k8s/unlimited-ocr-deploy.yaml

## Security

- **Sandboxed Parsing**: Untrusted documents processed in isolated worker containers.
- **Input Validation**: File type, size, and content checks on every upload.
- **Secret Masking**: API keys and PII redacted from logs and responses.
- **Rate Limiting**: Per-user quotas on the parse API.

## Performance

- **40% lower CER** than previous SOTA on long-form documents.
- **32K token** context handles documents up to ~10K tokens in one pass.
- **Throughput maintained** via vLLM/SGLang paged attention.

## Roadmap

- **MVP**: Single-page parsing, REST API, Docker deployment.
- **Beta**: Multi-page long-horizon parsing, batch jobs, caching.
- **Production**: GPU autoscaling, multi-backend inference, observability.
- **Enterprise**: On-prem model serving, SLA guarantees, custom fine-tunes.

## Contributing

We welcome contributions! Please check out our [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on adding new inference backends, parser modes, and test coverage.

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.""",
    }

    # Unique role phrases found only in each stage's system prompt (checked first).
    STAGE_ROLES = {
        "paper analysis": ("research paper analyst",),
        "srs generation": ("requirements engineer", "srs engineer"),
        "module design": ("software architect",),
        "user flow design": ("ux/flow designer", "user flow designer"),
        "sdlc plan": ("project manager", "sdlc planner"),
        "code generation": ("full-stack developer",),
        "debugging & review": ("code reviewer", "debug reviewer"),
        "deployment plan": ("devops engineer",),
        "final review": ("qa lead",),
        "readme generation": ("technical writer", "readme generator"),
    }

    # Fallback keywords used when the system prompt has no known role phrase.
    STAGE_KEYWORDS = {
        "paper analysis": ("paper analysis", "paper analyst"),
        "srs generation": ("srs generation", "srs document", "software requirements specification"),
        "module design": ("module design", "module architecture"),
        "user flow design": ("user flow", "ux design"),
        "sdlc plan": ("sdlc", "project plan"),
        "code generation": ("code generation", "generate code"),
        "debugging & review": ("code review", "debugging"),
        "deployment plan": ("deployment plan", "deployment"),
        "final review": ("final review",),
        "readme generation": ("readme", "project readme"),
    }

    DEFAULT_RESPONSE = """## [Dev Mode] LLM Response

This is a simulated response from the Collabuild MAS DevProvider.

No real LLM provider is configured. In production mode, this response would be
generated by an actual language model (OpenRouter, NVIDIA, Ollama, Claude, etc.).

To use a real provider:
1. Set an API key: `export OPENROUTER_API_KEY=sk-or-...`
2. Or configure in the web UI: Settings → Provider → enter credentials
3. Or use a local model: `ollama pull llama3.1` then select "ollama" provider

---
**DevProvider** — Collabuild MAS v{version}"""

    def __init__(self, name: str = "dev"):
        super().__init__(name)

    def chat(self, model: str, messages: list, temperature: float = 0.3,
             max_tokens: int = 4096) -> str:
        user_msg = ""
        system_msg = ""
        for m in messages:
            role = m.get("role", "")
            content = m.get("content", "")
            if role == "system":
                system_msg = content
            elif role == "user":
                user_msg = content

        lower_system = system_msg.lower()
        lower_user = user_msg.lower()
        combined = lower_system + " " + lower_user

        # 1) Match on the stage's unique role phrase in the system prompt first.
        for stage_key, roles in self.STAGE_ROLES.items():
            if any(role in lower_system for role in roles):
                return self.STAGE_RESPONSES[stage_key]

        # 2) Fallback: loose keyword match across system + user content.
        for stage_key, keywords in self.STAGE_KEYWORDS.items():
            if any(kw in combined for kw in keywords):
                return self.STAGE_RESPONSES[stage_key]

        return self.DEFAULT_RESPONSE.format(version="1.0.0")

    def chat_stream(self, model: str, messages: list, temperature: float = 0.3,
                    max_tokens: int = 4096) -> Iterator[str]:
        full = self.chat(model, messages, temperature, max_tokens)
        words = full.split()
        chunk_size = 3
        for i in range(0, len(words), chunk_size):
            yield " ".join(words[i:i + chunk_size]) + " "

    def list_models(self) -> list:
        return ["dev-model"]


# ═══════════════════════════════════════════════════════════════
# GGUF/GGML file discovery
# ═══════════════════════════════════════════════════════════════

def discover_local_models(search_paths: list = None) -> list:
    """Find .gguf and .ggml files on the filesystem."""
    if search_paths is None:
        search_paths = [
            os.path.expanduser("~/models"),
            os.path.expanduser("~/Downloads"),
            os.path.expanduser("~/.cache/huggingface/hub"),
            "/opt/models",
            "/usr/share/models",
            "./models",
        ]
    found = []
    seen = set()
    for base in search_paths:
        base = os.path.expanduser(base)
        if not os.path.isdir(base):
            continue
        for ext in ("*.gguf", "*.ggml"):
            for path in glob.glob(os.path.join(base, "**", ext), recursive=True):
                if path not in seen:
                    seen.add(path)
                    name = os.path.basename(path)
                    size_mb = os.path.getsize(path) / (1024 * 1024)
                    found.append({
                        "name": name,
                        "path": path,
                        "format": "GGUF" if path.endswith(".gguf") else "GGML",
                        "size_mb": round(size_mb, 1),
                    })
    return sorted(found, key=lambda x: x["name"])


# ═══════════════════════════════════════════════════════════════
# Bhashini AI — Indian Languages API (भाषिणी)
# ═══════════════════════════════════════════════════════════════

class BhashiniAIProvider(LLMProvider):
    """Bhashini AI — Indian Language Translation, Transliteration, and NLP.

    Bhashini (भाषिणी) is India's National Language Translation Mission.
    Provides:
      • Machine Translation (22+ Indian languages ↔ English, Hindi pivot)
      • Transliteration (script conversion)
      • Language detection
      • ASR (speech-to-text) and TTS (text-to-speech)
      • Indian language text generation via LLM pipeline

    API reference: https://bhashini.gov.in/api-docs
    Requires ULCA API key from https://bhashini.gov.in/ulca/user/signup

    Config:
        api_key (str): Bhashini ULCA API key (required)
        endpoint (str): API base URL (default: https://nlp.ulcai.com/api/v1)
        pipeline_config (dict): pipeline service IDs for translation,
                                transliteration, tts, asr
        default_target_lang (str): target language code (default: "en")
        default_source_lang (str): source language code (default: "" = auto-detect)
    """

    DEFAULT_ENDPOINT = "https://nlp.ulcai.com/api/v1"

    SUPPORTED_LANGUAGES = {
        "as": "Assamese", "bn": "Bengali", "brx": "Bodo", "doi": "Dogri",
        "gom": "Konkani", "gu": "Gujarati", "hi": "Hindi", "kn": "Kannada",
        "ks": "Kashmiri", "kok": "Konkani", "mai": "Maithili", "ml": "Malayalam",
        "mr": "Marathi", "mni": "Manipuri", "ne": "Nepali", "or": "Odia",
        "pa": "Punjabi", "sa": "Sanskrit", "sat": "Santali", "sd": "Sindhi",
        "ta": "Tamil", "te": "Telugu", "ur": "Urdu", "en": "English",
    }
    LANGUAGE_CODES = {v.lower(): k for k, v in SUPPORTED_LANGUAGES.items()}
    LANGUAGE_CODES.update({k: k for k in SUPPORTED_LANGUAGES})

    def __init__(self, api_key: str = "", endpoint: str = "",
                 name: str = "bhashini", default_target_lang: str = "en",
                 pipeline_config: dict = None):
        super().__init__(name)
        self.api_key = api_key or os.getenv("BHASHINI_API_KEY", "")
        self.endpoint = (endpoint or self.DEFAULT_ENDPOINT).rstrip("/")
        self.default_target_lang = default_target_lang
        self.pipeline_config = pipeline_config or {}

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "Accept": "application/json",
        }

    def _resolve_lang_code(self, lang: str) -> str:
        """Resolve language name/code to ISO 639-1 code."""
        if not lang:
            return self.default_target_lang
        lang_lower = lang.lower().strip()
        if lang_lower in self.SUPPORTED_LANGUAGES:
            return lang_lower
        return self.LANGUAGE_CODES.get(lang_lower, lang_lower)

    # ── Core API call ────────────────────────────────────────

    def _call_pipeline(self, service_id: str, input_text: str,
                       source_lang: str = "", target_lang: str = "",
                       task_type: str = "translation") -> str:
        """Call Bhashini ULCA pipeline service.

        Args:
            service_id: ULCA pipeline service ID or endpoint path
            input_text: text to process
            source_lang: source language code (auto-detect if empty)
            target_lang: target language code
            task_type: 'translation', 'transliteration', 'tts', 'asr', 'ner'
        """
        if not self.api_key:
            return "[BhashiniAI Error: BHASHINI_API_KEY not configured. Get one at https://bhashini.gov.in/ulca/user/signup]"

        import requests

        source = self._resolve_lang_code(source_lang) if source_lang else "auto"
        target = self._resolve_lang_code(target_lang) if target_lang else self.default_target_lang

        payload = {
            "pipelineTasks": [{
                "taskType": task_type,
                "config": {
                    "language": {
                        "sourceLanguage": source if source != "auto" else "en",
                        "targetLanguage": target,
                    },
                    "serviceId": service_id or "",
                }
            }],
            "inputData": {
                "input": [{"source": input_text}]
            },
        }

        try:
            r = requests.post(
                f"{self.endpoint}/pipeline",
                json=payload,
                headers=self._headers(),
                timeout=60,
            )
            r.raise_for_status()
            data = r.json()
            output = data.get("pipelineResponse", [{}])[0]
            output_data = output.get("output", [{}])[0]
            target_text = output_data.get("target", "")
            if target_text:
                return target_text
            return output_data.get("source", input_text)
        except requests.RequestException as e:
            log.warning(f"[bhashini] pipeline call failed: {e}")
            return f"[BhashiniAPI Error: {e}]"

    # ── Public API methods ────────────────────────────────────

    def translate(self, text: str, source_lang: str = "",
                  target_lang: str = "en") -> str:
        """Translate text between Indian languages / English.

        Args:
            text: text to translate
            source_lang: source language code or name ("" = auto-detect)
            target_lang: target language code or name (default: "en")

        Returns:
            Translated text
        """
        return self._call_pipeline(
            service_id="ai4bharat/indictrans-v2",
            input_text=text,
            source_lang=source_lang,
            target_lang=target_lang,
            task_type="translation",
        )

    def transliterate(self, text: str, source_lang: str = "hi",
                      target_lang: str = "en") -> str:
        """Transliterate text from one script to another.

        Example: Devanagari 'नमस्ते' → Latin 'namaste'
        """
        return self._call_pipeline(
            service_id="ai4bharat/indic-xlit",
            input_text=text,
            source_lang=source_lang,
            target_lang=target_lang,
            task_type="transliteration",
        )

    def detect_language(self, text: str) -> str:
        """Detect the language of the input text."""
        result = self._call_pipeline(
            service_id="ai4bharat/indic-ner",
            input_text=text,
            task_type="ner",
        )
        if result and result != text:
            return result
        return "en"

    def tts(self, text: str, lang: str = "hi") -> bytes:
        """Text-to-Speech: convert text to audio bytes (WAV).

        Args:
            text: text to synthesize
            lang: language code (default: "hi")

        Returns:
            WAV audio bytes (empty bytes on error)
        """
        if not self.api_key:
            return b""
        import requests
        lang_code = self._resolve_lang_code(lang)
        payload = {
            "pipelineTasks": [{
                "taskType": "tts",
                "config": {
                    "language": {"sourceLanguage": lang_code},
                    "serviceId": "ai4bharat/indic-tts",
                    "gender": "female",
                    "samplingRate": 16000,
                }
            }],
            "inputData": {
                "input": [{"source": text}]
            },
        }
        try:
            r = requests.post(
                f"{self.endpoint}/pipeline",
                json=payload,
                headers=self._headers(),
                timeout=120,
            )
            r.raise_for_status()
            data = r.json()
            audio_b64 = (data.get("pipelineResponse", [{}])[0]
                         .get("output", [{}])[0]
                         .get("audio", ""))
            if audio_b64:
                import base64
                return base64.b64decode(audio_b64)
        except Exception as e:
            log.warning(f"[bhashini] TTS failed: {e}")
        return b""

    # ── LLMProvider interface ────────────────────────────────

    def chat(self, model: str, messages: list, temperature: float = 0.3,
             max_tokens: int = 4096) -> str:
        """Chat: uses Bhashini translation pipeline for multi-lingual support.

        For Indian language inputs, translates → processes → translates back.
        For English inputs, uses the translate endpoint as a generation proxy.
        """
        # Extract user message
        user_msg = ""
        system_msg = ""
        for m in messages:
            role = m.get("role", "")
            content = m.get("content", "")
            if role == "system":
                system_msg = content
            elif role == "user":
                user_msg = content

        if not user_msg:
            return "[BhashiniAI: empty user message]"

        combined = user_msg
        if system_msg:
            combined = f"{system_msg}\n\n{user_msg}"

        # Detect if non-English input
        has_devanagari = any(ord(c) > 0x0900 and ord(c) < 0x097F for c in combined)
        has_tamil = any(ord(c) > 0x0B80 and ord(c) < 0x0BFF for c in combined)
        has_telugu = any(ord(c) > 0x0C00 and ord(c) < 0x0C7F for c in combined)
        has_bengali = any(ord(c) > 0x0980 and ord(c) < 0x09FF for c in combined)
        is_non_english = has_devanagari or has_tamil or has_telugu or has_bengali

        if is_non_english:
            translated_input = self.translate(combined, target_lang="en")
            result = translated_input
            translated_back = self.translate(result, source_lang="en", target_lang="auto")
            return translated_back or result
        else:
            return self.translate(combined, target_lang="en")

    def list_models(self) -> list:
        return [
            "translate-en", "translate-hi", "translate-ta", "translate-te",
            "translate-bn", "translate-mr", "translate-gu", "translate-kn",
            "translate-ml", "translate-or", "translate-pa", "translate-ur",
            "transliterate", "tts", "asr",
        ]

    def status(self) -> dict:
        return {
            "provider": "bhashini",
            "configured": bool(self.api_key),
            "languages": self.SUPPORTED_LANGUAGES,
            "default_target": self.default_target_lang,
            "capabilities": [
                "translation", "transliteration", "language_detection",
                "tts", "asr", "ner",
            ],
            "pipeline_config": self.pipeline_config,
        }


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════

PROVIDER_REGISTRY = {
    "openrouter": OpenRouterProvider,
    "nvidia": NvidiaProvider,
    "claude": ClaudeProvider,
    "anthropic": ClaudeProvider,
    "ollama": OllamaProvider,
    "koboldcpp": KoboldCPPProvider,
    "textgen": TextGenWebUIProvider,
    "textgenerationwebui": TextGenWebUIProvider,
    "text-generation-webui": TextGenWebUIProvider,
    "dev": DevProvider,
    "bhashini": BhashiniAIProvider,
    "bhashiniai": BhashiniAIProvider,
}

def create_provider(config: dict) -> LLMProvider:
    """Factory: create an LLM provider from a config dict.

    Config keys:
        provider (str): one of 'openrouter', 'nvidia', 'ollama', 'koboldcpp',
                        'textgen', 'claude', 'bhashini', 'dev', 'custom'
        api_key  (str): API key (for openrouter, nvidia, claude, bhashini)
        endpoint (str): server URL
        name     (str): optional override

    Dev fallback:
        provider="dev" activates the DevProvider which returns structured
        mock responses for offline pipeline testing. No API key required.

    Bhashini AI:
        provider="bhashini" activates the BhashiniAIProvider for Indian
        language translation, transliteration, TTS and NLP. Requires
        BHASHINI_API_KEY from https://bhashini.gov.in/ulca/user/signup
    """
    provider_type = config.get("provider", "openrouter").lower()
    cls = PROVIDER_REGISTRY.get(provider_type) or PROVIDER_REGISTRY.get(provider_type.replace("-", "").replace("_", ""))
    if not cls:
        log.warning(f"Unknown provider '{provider_type}', falling back to openrouter")
        cls = OpenRouterProvider

    kwargs = {"endpoint": config.get("endpoint", "")}
    if issubclass(cls, DevProvider):
        kwargs = {}
    elif issubclass(cls, BhashiniAIProvider):
        kwargs["api_key"] = config.get("api_key", "")
        kwargs["default_target_lang"] = config.get("default_target_lang", "en")
    elif issubclass(cls, OpenAICompatibleProvider):
        kwargs["api_key"] = config.get("api_key", "")
    elif issubclass(cls, ClaudeProvider):
        kwargs["api_key"] = config.get("api_key", "")
        if "model" in config:
            kwargs["model"] = config["model"]
    if "name" in config:
        kwargs["name"] = config["name"]

    return cls(**kwargs)
