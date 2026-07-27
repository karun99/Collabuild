"""
Collabuild MAS — Research Paper → Full-Stack Delivery Pipeline
Each stage is a configurable agent using any LLM provider (OpenRouter, Ollama, KoboldCPP, text-generation-webui).
Generates Mermaid UML diagrams at every stage.
"""
import os, json, re, time, logging
from dataclasses import dataclass, field
from typing import Optional
from .providers import LLMProvider, create_provider
from . import config as cfgmod

log = logging.getLogger("pipeline")

# ── Defaults ────────────────────────────────────────────────
DEFAULT_MODEL = "openrouter/free"

@dataclass
class StageResult:
    stage: str
    agent: str
    content: str
    mermaid: str = ""
    artifacts: dict = field(default_factory=dict)
    passed: bool = True
    notes: str = ""

class StageAgent:
    """Configurable agent for a pipeline stage — uses an LLMProvider."""
    def __init__(self, name: str, role: str, provider: Optional[LLMProvider] = None,
                 model: str = "", temperature: float = 0.3, max_tokens: int = 4096):
        self.name = name
        self.role = role
        self.provider = provider
        self.model = model or DEFAULT_MODEL
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._last_error = None

    def call(self, system_prompt: str, user_prompt: str) -> str:
        self._last_error = None
        if not self.provider:
            self._last_error = "No provider configured"
            return f"[{self.name}] No provider configured — skipping API call"
        try:
            return self.provider.chat_with_retry(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        except Exception as e:
            log.warning(f"[{self.name}] all retries failed: {e}")
            self._last_error = str(e)
            return f"Error: {e}"

    def extract_mermaid(self, text: str) -> str:
        patterns = [
            r'```mermaid\s*\n(.*?)```',
            r'```\s*\n(flowchart|sequenceDiagram|classDiagram|stateDiagram|graph\s+[A-Z]{2})\s*\n(.*?)```',
        ]
        for p in patterns:
            m = re.search(p, text, re.DOTALL)
            if m:
                code = m.group(1) if m.lastindex == 1 else m.group(0)
                return code.strip()
        return ""

# ═══════════════════════════════════════════════════════════════
# PIPELINE STAGES
# ═══════════════════════════════════════════════════════════════

class PaperAnalyzer(StageAgent):
    def run(self, paper_text: str) -> StageResult:
        sys = "You are an expert research paper analyst. Extract structured information."
        usr = f"""Analyze this research paper and return:
1. TITLE & AUTHORS
2. PROBLEM STATEMENT
3. KEY METHODOLOGY (step-by-step)
4. ALGORITHMS USED
5. ARCHITECTURE / MODEL DESIGN
6. DATASETS & METRICS
7. TECH STACK IMPLIED
8. LIMITATIONS & ASSUMPTIONS
9. REPRODUCIBILITY NOTES

Also generate a Mermaid flowchart of the methodology.

PAPER:
{paper_text[:8000]}"""
        content = self.call(sys, usr)
        mermaid = self.extract_mermaid(content)
        if not mermaid:
            mermaid = """flowchart TD
    A[Research Paper] --> B[Problem Definition]
    B --> C[Methodology]
    C --> D[Algorithm Design]
    D --> E[Implementation]
    E --> F[Evaluation]
    F --> G[Results]
    G --> H[Conclusions]"""
        passed = self._last_error is None
        return StageResult(stage="Paper Analysis", agent=self.name, content=content, mermaid=mermaid, passed=passed)

class SRSGenerator(StageAgent):
    def run(self, paper_result: str) -> StageResult:
        sys = "You are an expert requirements engineer. Generate a comprehensive SRS document."
        usr = f"""Based on this research paper analysis, generate a Software Requirements Specification (IEEE 830 style):

1. INTRODUCTION — Purpose, scope, definitions
2. OVERALL DESCRIPTION — Product perspective, user characteristics, constraints
3. SPECIFIC REQUIREMENTS — Functional (use-case driven), Non-functional (performance, security, scalability)
4. SYSTEM FEATURES — Modules identified
5. EXTERNAL INTERFACE REQUIREMENTS — User, hardware, software, communication
6. DATA REQUIREMENTS — Data models, formats, storage
7. ASSUMPTIONS & DEPENDENCIES

Also generate a Mermaid use case diagram for the system.

PAPER ANALYSIS:
{paper_result[:6000]}"""
        content = self.call(sys, usr)
        mermaid = self.extract_mermaid(content)
        if not mermaid:
            mermaid = """graph LR
    U[User] -->|Upload Document| S[System]
    S -->|Parse| OCR[OCR Engine]
    S -->|Analyze| AI[AI Model]
    S -->|Generate| Out[Output]
    Out -->|View| U
    Out -->|Download| U"""
        passed = self._last_error is None
        return StageResult(stage="SRS Generation", agent=self.name, content=content, mermaid=mermaid, passed=passed)

class ModuleDesigner(StageAgent):
    def run(self, srs_result: str) -> StageResult:
        sys = "You are an expert software architect. Design the module architecture."
        usr = f"""Based on this SRS, design the complete module architecture:

1. HIGH-LEVEL ARCHITECTURE — System context, layers
2. MODULE DECOMPOSITION — Each module: name, responsibility, inputs, outputs, dependencies
3. MODULE INTERFACES — API contracts between modules
4. DATA FLOW — How data moves between modules
5. TECHNOLOGY RECOMMENDATIONS — Per module

Also generate a Mermaid class diagram showing the module structure.

SRS:
{srs_result[:6000]}"""
        content = self.call(sys, usr)
        mermaid = self.extract_mermaid(content)
        if not mermaid:
            mermaid = """classDiagram
    class DocumentProcessor {
        +load(file) Document
        +preprocess() Document
    }
    class OCREngine {
        +extractText(Document) string
        +parseLayout() Layout
    }
    class AIAnalyzer {
        +analyze(string) Analysis
        +classify() Category
    }
    class OutputGenerator {
        +format(Analysis) Output
        +export(format) File
    }
    DocumentProcessor --> OCREngine
    OCREngine --> AIAnalyzer
    AIAnalyzer --> OutputGenerator"""
        return StageResult(stage="Module Design", agent=self.name, content=content, mermaid=mermaid, passed=self._last_error is None)

class UserFlowDesigner(StageAgent):
    def run(self, module_result: str) -> StageResult:
        sys = "You are an expert UX/flow designer. Design detailed user interaction flows."
        usr = f"""Based on the module architecture, design complete user flows:

1. PRIMARY FLOW — Happy path step-by-step
2. SECONDARY FLOWS — Alternative paths
3. ERROR FLOWS — Error handling for each step
4. USER DECISIONS — Branching points in the UI
5. SCREEN-TO-SCREEN FLOW — Navigation map

Generate a Mermaid sequence diagram for the primary user flow, and a flowchart for navigation.

MODULE ARCHITECTURE:
{module_result[:6000]}"""
        content = self.call(sys, usr)
        mermaid = self.extract_mermaid(content)
        if not mermaid:
            mermaid = """sequenceDiagram
    actor User
    participant UI as Web App
    participant API as Backend API
    participant OCR as OCR Service
    participant AI as AI Engine
    participant DB as Database
    User->>UI: Upload Document
    UI->>API: POST /api/process
    API->>OCR: extract_text(document)
    OCR-->>API: raw_text
    API->>AI: analyze(raw_text)
    AI-->>API: structured_data
    API->>DB: store(result)
    API-->>UI: {result_id}
    UI-->>User: Display Results"""
        return StageResult(stage="User Flow Design", agent=self.name, content=content, mermaid=mermaid, passed=self._last_error is None)

class SDLCPlanner(StageAgent):
    def run(self, module_result: str, flow_result: str) -> StageResult:
        sys = "You are an expert project manager. Create a detailed SDLC plan."
        usr = f"""Create a complete SDLC project plan:

1. PHASES — Requirements → Design → Implementation → Testing → Deployment → Maintenance
2. SPRINT BREAKDOWN — 2-week sprints with specific deliverables
3. TASK DEPENDENCIES — What blocks what
4. MILESTONES — Key checkpoints with success criteria
5. RESOURCE PLAN — Roles needed (developers, QA, DevOps, PM)
6. RISK ASSESSMENT — Top 5 risks and mitigation
7. TIMELINE — Estimated duration per phase

Generate a Mermaid Gantt chart for the project timeline.

MODULES: {module_result[:3000]}
FLOWS: {flow_result[:3000]}"""
        content = self.call(sys, usr)
        mermaid = self.extract_mermaid(content)
        if not mermaid:
            mermaid = """gantt
    title Project Timeline
    dateFormat  YYYY-MM-DD
    section Requirements
    Paper Analysis           :a1, 2026-01-01, 5d
    SRS Generation           :a2, after a1, 5d
    section Design
    Architecture Design      :b1, after a2, 7d
    Module Specs             :b2, after b1, 5d
    section Implementation
    Core Engine              :c1, after b2, 15d
    API Layer                :c2, after c1, 10d
    Frontend                 :c3, after c2, 12d
    section Testing
    Integration Tests        :d1, after c3, 7d
    Performance Testing      :d2, after d1, 5d
    section Deployment
    Staging                  :e1, after d2, 3d
    Production               :e2, after e1, 2d"""
        return StageResult(stage="SDLC Plan", agent=self.name, content=content, mermaid=mermaid, passed=self._last_error is None)

class CodeGenerator(StageAgent):
    def run(self, module_result: str, flow_result: str, sdlc_result: str) -> StageResult:
        sys = "You are an expert full-stack developer. Generate production-ready code."
        usr = f"""Generate implementation code for the core modules. For each file, provide:

1. FILE PATH — e.g., src/ocr/engine.py
2. PURPOSE — What this file does
3. DEPENDENCIES — What it imports
4. CODE — Complete implementation with error handling, logging, type hints
5. TESTS — Basic test structure

Focus on:
- OCR document processing module (core engine)
- API layer (FastAPI/Flask endpoints)
- Data models (Pydantic/SQLAlchemy)
- Configuration and entry point

MODULE ARCH: {module_result[:3000]}
USER FLOW: {flow_result[:2000]}
SDLC: {sdlc_result[:2000]}"""
        content = self.call(sys, usr)
        mermaid = self.extract_mermaid(content)
        return StageResult(stage="Code Generation", agent=self.name, content=content, mermaid=mermaid, passed=self._last_error is None)

class Debugger(StageAgent):
    def run(self, code_result: str) -> StageResult:
        sys = "You are an expert code reviewer. Find bugs, security flaws, and performance issues."
        usr = f"""Review this generated code. Check for:

1. BUGS — Logic errors, edge cases, race conditions
2. SECURITY — Injection, auth flaws, data exposure, dependency risks
3. PERFORMANCE — N+1 queries, memory leaks, slow algorithms
4. CODE QUALITY — DRY violations, complexity, naming, comments
5. TEST COVERAGE — Missing test cases
6. FIXES — Provide corrected code for each issue

For each issue: SEVERITY (CRITICAL/HIGH/MEDIUM/LOW), DESCRIPTION, FIX.

CODE:
{code_result[:8000]}"""
        content = self.call(sys, usr)
        return StageResult(stage="Debugging & Review", agent=self.name, content=content, passed=self._last_error is None)

class DeploymentPlanner(StageAgent):
    def run(self, code_result: str, debug_result: str) -> StageResult:
        sys = "You are an expert DevOps engineer. Design the deployment infrastructure."
        usr = f"""Design the complete deployment plan:

1. INFRASTRUCTURE — Cloud provider, regions, scaling strategy
2. CONTAINERIZATION — Docker setup, multi-stage builds
3. ORCHESTRATION — K8s / Docker Compose config
4. CI/CD — Pipeline stages (build, test, deploy)
5. MONITORING — Logging, metrics, alerts
6. ENVIRONMENT CONFIG — Dev, Staging, Production differences
7. COST ESTIMATE — Monthly running cost breakdown

Generate a Mermaid deployment diagram.

CODE ARCHITECTURE: {code_result[:3000]}
REVIEW NOTES: {debug_result[:2000]}"""
        content = self.call(sys, usr)
        mermaid = self.extract_mermaid(content)
        if not mermaid:
            mermaid = """graph TB
    subgraph "Production Environment"
        LB[Load Balancer]
        subgraph "App Servers"
            A1[App Instance 1]
            A2[App Instance 2]
        end
        subgraph "AI Cluster"
            GPU1[GPU Node 1]
            GPU2[GPU Node 2]
        end
        DB[(Database)]
        Cache[(Redis Cache)]
        Storage[(Object Storage)]
    end
    User --> LB
    LB --> A1 & A2
    A1 & A2 --> DB & Cache
    A1 & A2 --> GPU1 & GPU2
    A1 & A2 --> Storage"""
        return StageResult(stage="Deployment Plan", agent=self.name, content=content, mermaid=mermaid, passed=self._last_error is None)

class FinalReviewer(StageAgent):
    def run(self, all_results: dict) -> StageResult:
        sys = "You are an expert QA lead. Perform final validation of the entire pipeline output."
        usr = f"""Review the complete pipeline output. For each area, give a PASS/FAIL with evidence:

1. ACCURACY — Does the output match the paper? Are algorithms preserved correctly?
2. COMPLETENESS — Are all paper contributions addressed in the SRS and modules?
3. EFFICIENCY — Are the recommended tech stack and architecture performant?
4. FEASIBILITY — Can this be built within typical constraints?
5. REPRODUCIBILITY — Can someone implement this paper from these outputs?
6. GAP ANALYSIS — What's missing between paper and production-ready app?

Pipeline summary:
{json.dumps({k: str(v)[:500] for k, v in all_results.items()}, indent=2)}"""
        content = self.call(sys, usr)
        all_passed = self._last_error is None
        if "FAIL" in content.upper():
            parts = content.upper().split("PASS")
            if parts and "FAIL" in parts[0]:
                all_passed = False
        return StageResult(stage="Final Review", agent=self.name, content=content, passed=all_passed)

# ═══════════════════════════════════════════════════════════════
# ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════

class CollabuildPipeline:
    def __init__(self, provider: Optional[LLMProvider] = None, model: str = "",
                 api_key: str = "", endpoint: str = ""):
        if provider:
            self.provider = provider
        elif api_key or endpoint:
            self.provider = create_provider({"api_key": api_key, "endpoint": endpoint})
        else:
            self.provider = None

        model = model or DEFAULT_MODEL
        kw = dict(provider=self.provider, model=model)
        self.stages = {
            "paper_analysis":  PaperAnalyzer("Paper-Analyzer", "research paper analyst", **kw),
            "srs":             SRSGenerator("SRS-Engineer", "requirements engineer", **kw),
            "module_design":   ModuleDesigner("Module-Architect", "software architect", **kw),
            "user_flow":       UserFlowDesigner("UX-Designer", "user flow designer", **kw),
            "sdlc_plan":       SDLCPlanner("SDLC-Planner", "project manager", **kw),
            "code_gen":        CodeGenerator("Code-Gen", "full-stack developer", **{**kw, "temperature": 0.2, "max_tokens": 8192}),
            "debug":           Debugger("Debug-Reviewer", "code reviewer", **{**kw, "temperature": 0.1}),
            "deployment":      DeploymentPlanner("DevOps-Architect", "DevOps engineer", **kw),
            "final_review":    FinalReviewer("QA-Reviewer", "QA lead", **{**kw, "temperature": 0.1}),
        }
        self.results = {}

    @classmethod
    def from_config(cls, config_path: str = "", provider_name: str = "") -> "CollabuildPipeline":
        cfg = cfgmod.load(config_path)
        ai_cfg = cfgmod.get_ai_config(cfg)
        if provider_name:
            ai_cfg["provider"] = provider_name
        provider = create_provider(ai_cfg)
        model = ai_cfg.get("model", DEFAULT_MODEL)
        return cls(provider=provider, model=model)

    @classmethod
    def from_config_dict(cls, cfg: dict) -> "CollabuildPipeline":
        """Create pipeline from a plain dict (e.g. from CLI args or get_ai_config)."""
        provider = create_provider(cfg)
        model = cfg.get("model", DEFAULT_MODEL)
        return cls(provider=provider, model=model)

    def run(self, paper_text: str) -> dict:
        log.info("=" * 60)
        log.info("Collabuild MAS Pipeline: Research Paper → Full-Stack App")
        log.info("=" * 60)

        log.info("\n[1/9] Analyzing research paper...")
        r1 = self.stages["paper_analysis"].run(paper_text)
        self.results["paper_analysis"] = r1
        log.info(f"  -> Paper: {r1.content[:100]}...")

        log.info("\n[2/9] Generating SRS...")
        r2 = self.stages["srs"].run(r1.content)
        self.results["srs"] = r2
        log.info(f"  -> SRS generated ({len(r2.content)} chars)")

        log.info("\n[3/9] Designing modules...")
        r3 = self.stages["module_design"].run(r2.content)
        self.results["module_design"] = r3

        log.info("\n[4/9] Designing user flows...")
        r4 = self.stages["user_flow"].run(r3.content)
        self.results["user_flow"] = r4

        log.info("\n[5/9] Creating SDLC plan...")
        r5 = self.stages["sdlc_plan"].run(r3.content, r4.content)
        self.results["sdlc_plan"] = r5

        log.info("\n[6/9] Generating code...")
        r6 = self.stages["code_gen"].run(r3.content, r4.content, r5.content)
        self.results["code_gen"] = r6

        log.info("\n[7/9] Debugging & reviewing code...")
        r7 = self.stages["debug"].run(r6.content)
        self.results["debug"] = r7

        log.info("\n[8/9] Planning deployment...")
        r8 = self.stages["deployment"].run(r6.content, r7.content)
        self.results["deployment"] = r8

        log.info("\n[9/9] Final review...")
        flat = {k: str(v.content)[:500] for k, v in self.results.items()}
        r9 = self.stages["final_review"].run(flat)
        self.results["final_review"] = r9

        log.info("\n" + "=" * 60)
        log.info("Pipeline complete!")
        log.info("=" * 60)
        return self.results

    def report(self) -> str:
        lines = ["# Collabuild MAS — Pipeline Report", ""]
        for name, r in self.results.items():
            title = r.stage
            lines.append(f"## {title}")
            lines.append(f"**Agent:** {r.agent}  ")
            lines.append(f"**Status:** {'✅ PASS' if r.passed else '❌ FAIL'}  ")
            if r.mermaid:
                lines.append("\n### Diagram\n")
                lines.append("```mermaid")
                lines.append(r.mermaid)
                lines.append("```")
            lines.append("\n### Output\n")
            lines.append(r.content)
            lines.append("\n---\n")
        return "\n".join(lines)
