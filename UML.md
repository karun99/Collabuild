# Collabuild MAS — UML Diagrams

All diagrams are in [Mermaid](https://mermaid-js.github.io/) format. Render at [mermaid.live](https://mermaid.live) or in any Mermaid-compatible viewer.

---

## 1. System Architecture

```mermaid
graph TB
    subgraph "Browser (Web UI)"
        UI[Chat Interface]
        SP[Settings Panel]
        PL[Pipeline Runner]
        TL[Research Tools]
    end

    subgraph "FastAPI Backend"
        API["/api/chat (SSE)"]
        ST["/api/settings"]
        MD["/api/models"]
        PW["/api/pipeline/*"]
        TL_API["/api/tools/*"]
    end

    subgraph "LLM Providers"
        OR[OpenRouter]
        NV[NVIDIA Build]
        CL[Claude]
        OL[Ollama]
        KC[KoboldCPP]
        TG[text-gen-webui]
        DV[DevProvider]
    end

    subgraph "Research Tools"
        OCR[Baidu OCR]
        WF[Web Fetcher]
        AR[Agent Runner]
    end

    subgraph "Pipeline Stages"
        P1[Paper Analysis]
        P2[SRS Generation]
        P3[Module Design]
        P4[User Flow Design]
        P5[SDLC Plan]
        P6[Code Generation]
        P7[Debugging & Review]
        P8[Deployment Plan]
        P9[Final Review]
    end

    UI --> API
    SP --> ST
    PL --> PW
    TL --> TL_API

    API --> OR & NV & CL & OL & KC & TG & DV
    PW --> P1 --> P2 --> P3 --> P4 --> P5 --> P6 --> P7 --> P8 --> P9

    TL_API --> OCR & WF & AR
```

---

## 2. Provider Class Hierarchy

```mermaid
classDiagram
    class LLMProvider {
        <<abstract>>
        +name: str
        +chat(model, messages, temperature, max_tokens) str
        +chat_stream(model, messages, temperature, max_tokens) Iterator
        +list_models() list
        +chat_with_retry(model, messages, temperature, max_tokens, retries) str
    }

    class OpenAICompatibleProvider {
        +endpoint: str
        +api_key: str
        +extra_headers: dict
        +_headers() dict
        +chat() str
        +chat_stream() Iterator
        +list_models() list
    }

    class OpenRouterProvider {
        +api_key: str
    }

    class NvidiaProvider {
        +api_key: str
    }

    class TextGenWebUIProvider {
        +endpoint: str
    }

    class ClaudeProvider {
        +endpoint: str
        +api_key: str
        +model: str
        +_headers() dict
        +chat() str
        +chat_stream() Iterator
        +list_models() list
    }

    class OllamaProvider {
        +endpoint: str
        +chat() str
        +chat_stream() Iterator
        +list_models() list
    }

    class KoboldCPPProvider {
        +endpoint: str
        +chat() str
        +chat_stream() Iterator
        +list_models() list
    }

    class DevProvider {
        +STAGE_RESPONSES: dict
        +DEFAULT_RESPONSE: str
        +chat() str
        +chat_stream() Iterator
        +list_models() list
    }

    LLMProvider <|-- OpenAICompatibleProvider
    LLMProvider <|-- ClaudeProvider
    LLMProvider <|-- OllamaProvider
    LLMProvider <|-- KoboldCPPProvider
    LLMProvider <|-- DevProvider
    OpenAICompatibleProvider <|-- OpenRouterProvider
    OpenAICompatibleProvider <|-- NvidiaProvider
    OpenAICompatibleProvider <|-- TextGenWebUIProvider
```

---

## 3. 10-Stage Pipeline Flow

```mermaid
flowchart TD
    A[/"Research Paper Input"/] --> B["1. Paper Analysis\n(PaperAnalyzer)"]
    B --> C["2. SRS Generation\n(SRSGenerator)"]
    C --> D["3. Module Design\n(ModuleDesigner)"]
    D --> E["4. User Flow Design\n(UserFlowDesigner)"]
    E --> F["5. SDLC Plan\n(SDACPlanner)"]
    F --> G["6. Code Generation\n(CodeGenerator)"]
    G --> H["7. Debugging & Review\n(Debugger)"]
    H --> I["8. Deployment Plan\n(DeploymentPlanner)"]
    I --> J["9. Final Review\n(FinalReviewer)"]
    J --> K[/"Pipeline Report\n(Markdown + Mermaid)"/]

    style A fill:#7aa2f7,stroke:#333,color:#fff
    style K fill:#9ece6a,stroke:#333,color:#fff
    style B fill:#24283b,stroke:#7aa2f7,color:#c0caf5
    style C fill:#24283b,stroke:#7aa2f7,color:#c0caf5
    style D fill:#24283b,stroke:#7aa2f7,color:#c0caf5
    style E fill:#24283b,stroke:#7aa2f7,color:#c0caf5
    style F fill:#24283b,stroke:#7aa2f7,color:#c0caf5
    style G fill:#24283b,stroke:#bb9af7,color:#c0caf5
    style H fill:#24283b,stroke:#f7768e,color:#c0caf5
    style I fill:#24283b,stroke:#7aa2f7,color:#c0caf5
    style J fill:#24283b,stroke:#9ece6a,color:#c0caf5
```

---

## 4. Chat API Sequence Diagram

```mermaid
sequenceDiagram
    actor User
    participant Browser
    participant FastAPI
    participant Provider
    participant LLM

    User->>Browser: Type message & send
    Browser->>FastAPI: POST /api/chat<br/>{messages, model, provider}
    FastAPI->>FastAPI: Build messages with system prompt
    FastAPI->>Provider: create_provider(settings)
    Provider-->>FastAPI: LLMProvider instance

    loop Streaming (SSE)
        Provider->>LLM: chat_stream(model, messages)
        loop Each token
            LLM-->>Provider: token string
            Provider-->>FastAPI: yield token
            FastAPI-->>Browser: event: token\ndata: {token}
        end
        LLM-->>Provider: [DONE]
        Provider-->>FastAPI: yield ""
    end

    FastAPI-->>Browser: event: done\ndata:
    Browser-->>User: Render streamed response
```

---

## 5. Provider Selection Sequence

```mermaid
sequenceDiagram
    actor User
    participant UI as Settings UI
    participant API as /api/settings
    participant Disk as settings.json
    participant Provider as _get_provider()

    User->>UI: Select provider + enter credentials
    UI->>API: POST /api/settings<br/>{provider, api_key, endpoint, model}
    API->>Disk: Write settings.json
    API-->>UI: {ok: true}

    Note over User,Provider: Next chat request
    User->>UI: Send message
    UI->>API: POST /api/chat
    API->>Provider: _get_provider(user_settings)
    Provider->>Provider: Merge config.yaml + user_settings
    Provider-->>API: LLMProvider instance
    API->>Provider: chat_stream(messages)
    Provider-->>API: token stream
    API-->>UI: SSE events
```

---

## 6. Multi-Agent System (MAS) Class Diagram

```mermaid
classDiagram
    class AgentConfig {
        +name: str
        +role: str
        +endpoint: str
        +auth_type: AuthType
        +api_key: str
        +model: str
        +temperature: float
        +max_tokens: int
        +auth_headers() dict
        +endpoint_url(path) str
    }

    class AuthType {
        <<enum>>
        NONE
        BEARER
        API_KEY
        HEADER
        BASIC
        CUSTOM
    }

    class ProcessType {
        <<enum>>
        SEQUENTIAL
        HIERARCHICAL
        PARALLEL
    }

    class Agent {
        +config: AgentConfig
        +run(task) any
        +_local_fn(task) str
        +_call_api(task) str
    }

    class OCRAgent {
        +_call_api(task) str
        +_openai_vision(task, file_path) str
        +_generic_ocr(task) str
    }

    class DocumentAnalyzer
    class QualityChecker

    class Task {
        +id: str
        +description: str
        +agent: str
        +context: dict
        +expected_output: str
        +callback: Callable
        +dependencies: list
        +result: any
    }

    class Crew {
        +agents: dict
        +tasks: list
        +process: ProcessType
        +kickoff() list
        +_run_sequential() list
        +_run_parallel() list
        +_run_hierarchical() list
        +summary() str
    }

    AgentConfig --> AuthType
    Agent --> AgentConfig
    OCRAgent --|> Agent
    DocumentAnalyzer --|> Agent
    QualityChecker --|> Agent
    Crew --> Agent
    Crew --> Task
    Crew --> ProcessType
    Task --> Agent : assigned to
```

---

## 7. Pipeline Stage Agent Flow

```mermaid
flowchart LR
    subgraph StageAgent
        A[call system_prompt, user_prompt] --> B{provider configured?}
        B -->|No| C[Return skip message]
        B -->|Yes| D[provider.chat_with_retry]
        D --> E{Success?}
        E -->|Yes| F[Return content]
        E -->|No| G[Log error, return error]
        F --> H[extract_mermaid]
        H --> I{Mermaid found?}
        I -->|Yes| J[Use extracted mermaid]
        I -->|No| K[Use fallback mermaid]
    end
```

---

## 8. Web Application Deployment

```mermaid
graph TB
    subgraph "Client"
        Browser[Web Browser]
    end

    subgraph "Docker Container"
        subgraph "Python 3.12"
            UV[uvicorn]
            FA[FastAPI app]
            subgraph "Routes"
                R1["/ (Chat)"]
                R2["/settings"]
                R3["/pipeline"]
                R4["/tools"]
                R5["/api/*"]
            end
        end
    end

    subgraph "External Services"
        OR_API[OpenRouter API]
        NV_API[NVIDIA API]
        CL_API[Claude API]
        BD_API[Baidu OCR API]
    end

    subgraph "Local Services"
        OL_SVR[Ollama :11434]
        KC_SVR[KoboldCPP :5001]
        TG_SVR[text-gen-webui :5000]
    end

    Browser -->|HTTP/SSE| UV
    UV --> FA
    FA --> R1 & R2 & R3 & R4 & R5
    R5 --> OR_API & NV_API & CL_API & BD_API
    R5 --> OL_SVR & KC_SVR & TG_SVR
```

---

## 9. Research Agent Loop

```mermaid
flowchart TD
    A[/"User Task"/] --> B["Initialize AgentRunner"]
    B --> C["LLM: Analyze task"]
    C --> D{"Has tool_calls?"}
    D -->|Yes| E["Execute tools\n(web_fetch, ocr, python)"]
    E --> F["Feed results back to LLM"]
    F --> C
    D -->|No| G{"Has output?"}
    G -->|Yes| H[/"Final Answer"/]
    G -->|No| I{Steps < max?}
    I -->|Yes| C
    I -->|No| J["Force synthesis"]
    J --> H

    style A fill:#7aa2f7,stroke:#333,color:#fff
    style H fill:#9ece6a,stroke:#333,color:#fff
    style E fill:#e0af68,stroke:#333,color:#fff
```

---

## 10. Data Flow — OCR Document Processing

```mermaid
flowchart LR
    A[/"Document\n(PDF/DOC/Image)"/] --> B["BaiduOCR\n.parse_document()"]
    B --> C["_submit_document()\nNormalize UTF-8"]
    C --> D["POST /unlimited-ocr-parser/task"]
    D --> E["task_id"]
    E --> F["_poll_task()\nStatus check loop"]
    F --> G{"Status?"}
    G -->|success| H["markdown_url"]
    G -->|pending| F
    G -->|failed| I["RuntimeError"]
    H --> J["_download_markdown()\nDecode UTF-8/16/32"]
    J --> K[/"Markdown Text"/]

    style A fill:#7aa2f7,stroke:#333,color:#fff
    style K fill:#9ece6a,stroke:#333,color:#fff
    style I fill:#f7768e,stroke:#333,color:#fff
```

---

## 11. Configuration Resolution

```mermaid
flowchart TD
    A["config.yaml"] --> B["load()"]
    B --> C["_resolve_env()\nSubstitute ${ENV_VAR}"]
    C --> D["get_ai_config()"]
    D --> E["Merge: provider defaults"]
    E --> F["Merge: chat defaults"]
    F --> G["CLI overrides\n(--provider, --api-key, etc.)"]
    G --> H["create_provider(config)"]
    H --> I{"Provider type?"}
    I -->|openrouter| J[OpenRouterProvider]
    I -->|nvidia| K[NvidiaProvider]
    I -->|claude| L[ClaudeProvider]
    I -->|ollama| M[OllamaProvider]
    I -->|koboldcpp| N[KoboldCPPProvider]
    I -->|textgen| O[TextGenWebUIProvider]
    I -->|dev| P[DevProvider]
```

---

## 12. CI/CD Pipeline

```mermaid
flowchart LR
    subgraph "GitHub Actions"
        A[Push to main/develop] --> B["Test Job"]
        B --> B1["Python 3.10-3.13 matrix"]
        B1 --> B2["ruff check"]
        B2 --> B3["pytest"]
        B3 --> B4["python -m build"]
        B4 --> B5["Verify wheel contents"]

        B5 --> C["Build Job"]
        C --> C1["Build wheel + sdist"]
        C1 --> C2["Upload artifacts"]

        C2 --> D{"Tag push?"}
        D -->|Yes| E["Publish Job"]
        E --> E1["Download artifacts"]
        E1 --> E2["pypa/gh-action-pypi-publish"]
        D -->|No| F[Done]
    end
```

---

## 13. Module Decomposition

```mermaid
graph TB
    subgraph "collabuild/"
        INIT["__init__.py\nPackage exports"]
        MAIN["__main__.py\nCLI entry point (pipeline, web, reach, devsrs)"]
        CFG["config.py\nYAML loader + env vars"]
        PROV["providers.py\nLLM providers (7+)"]
        MAS["mas.py\nAgent, Crew, Task framework"]
        PIPE["pipeline.py\n10-stage pipeline + write_artifacts()"]
        DSRS["devsrs.py\nDevSRS — SRS → cli/web/mcp app"]
        REACH["reach/\nAgent-Reach capability layer"]

        subgraph "ocr/"
            BaiduOCR["baidu_ocr.py\nBaidu Unlimited-OCR + General OCR"]
        end

        subgraph "research/"
            WF["web_fetcher.py\nURL fetching + text extraction"]
            AR["agent_runner.py\nAutonomous research agent"]
        end

        subgraph "web/"
            APP["app.py\nFastAPI routes + API"]
            subgraph "templates/"
                T1["chat.html"]
                T2["settings.html"]
                T3["pipeline.html"]
                T4["tools.html"]
                T5["base.html"]
            end
        end
    end

    MAIN --> CFG & PIPE & DSRS
    PIPE --> PROV
    PIPE --> DSRS
    DSRS --> PROV
    APP --> PROV & CFG
    AR --> WF
    AR --> BaiduOCR
```

---

## 14. DevSRS Build Flow

```mermaid
graph LR
    SRS["SRS.md\n(IEEE 830 draft)"] --> PARSE["parse_srs()"]
    PARSE --> BP["SRSBlueprint\nmodules / features / tech stack"]

    BP --> CLI["target: cli\nmain.py + core.py + agents.py"]
    BP --> WEB["target: web\nFastAPI app + static/"]
    BP --> MCP["target: mcp\nJSON-RPC server.py"]

    CLI --> SMOKE["Smoke tests\npy_compile + run --list"]
    WEB --> SMOKE2["Smoke tests\npy_compile + uvicorn"]
    MCP --> SMOKE3["Smoke tests\nMCP tools/list + tools/call"]
    SMOKE & SMOKE2 & SMOKE3 --> OUT["generated_app/\nREADME.md + tests + Dockerfile"]
```

---

## Rendering

To render these diagrams:

1. **Online:** Copy any ```mermaid block into [mermaid.live](https://mermaid.live)
2. **VS Code:** Install the "Mermaid Preview" extension
3. **GitHub:** Markdown files with Mermaid blocks render automatically on GitHub
4. **CLI:** Use `mmdc` (Mermaid CLI):
   ```bash
   npm install -g @mermaid-js/mermaid-cli
   mmdc -i diagram.mmd -o diagram.svg
   ```
