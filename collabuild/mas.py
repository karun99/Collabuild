"""
Collabuild MAS — Multi-Agent System (CrewAI-like)
Configurable agents with endpoint + auth for distributed AI workflows.
"""
import base64
import json
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
log = logging.getLogger("mas")

class AuthType(Enum):
    NONE    = "none"
    BEARER  = "bearer"
    API_KEY = "api_key"       # ?api_key=...
    HEADER  = "header"         # custom header key:value
    BASIC   = "basic"
    CUSTOM  = "custom"

class ProcessType(Enum):
    SEQUENTIAL = "sequential"
    HIERARCHICAL = "hierarchical"
    PARALLEL = "parallel"

@dataclass
class AgentConfig:
    name: str
    role: str = "assistant"
    endpoint: str = ""
    auth_type: AuthType = AuthType.NONE
    api_key: str = ""
    api_key_header: str = "Authorization"   # for HEADER type
    api_key_prefix: str = "Bearer "         # for HEADER/BEARER
    model: str = "gpt-4o"
    extra_headers: dict = field(default_factory=dict)
    timeout: int = 120
    max_retries: int = 3
    temperature: float = 0.3
    max_tokens: int = 4096
    tools: list = field(default_factory=list)

    def auth_headers(self) -> dict:
        h = dict(self.extra_headers)
        if self.auth_type == AuthType.BEARER:
            h["Authorization"] = f"Bearer {self.api_key}"
        elif self.auth_type == AuthType.API_KEY:
            h["api_key"] = self.api_key
        elif self.auth_type == AuthType.HEADER:
            h[self.api_key_header] = f"{self.api_key_prefix}{self.api_key}"
        elif self.auth_type == AuthType.BASIC:
            import base64
            raw = base64.b64encode(self.api_key.encode()).decode()
            h["Authorization"] = f"Basic {raw}"
        return h

    def endpoint_url(self, path: str = "") -> str:
        return self.endpoint.rstrip("/") + ("/" + path.lstrip("/") if path else "")

@dataclass
class Task:
    id: str = ""
    description: str = ""
    agent: str | None = None       # agent name
    context: dict = field(default_factory=dict)
    expected_output: str = ""
    callback: Callable | None = None
    dependencies: list = field(default_factory=list)
    result: any = None

class Agent:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.log = logging.getLogger(f"agent.{config.name}")

    def run(self, task: Task) -> any:
        if not self.config.endpoint:
            return self._local_fn(task)
        return self._call_api(task)

    def _local_fn(self, task: Task) -> str:
        self.log.info(f"[local] {task.description}")
        return f"[{self.config.name}] processed: {task.description}"

    def _call_api(self, task: Task) -> str:
        url = self.config.endpoint_url("v1/chat/completions")
        headers = {"Content-Type": "application/json", **self.config.auth_headers()}
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": f"You are {self.config.name}, {self.config.role}."},
                {"role": "user", "content": json.dumps({"task": task.description, "context": task.context})}
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        for attempt in range(self.config.max_retries):
            try:
                r = requests.post(url, json=payload, headers=headers, timeout=self.config.timeout)
                r.raise_for_status()
                data = r.json()
                return data["choices"][0]["message"]["content"]
            except Exception as e:
                self.log.warning(f"attempt {attempt+1}/{self.config.max_retries} failed: {e}")
                if attempt == self.config.max_retries - 1:
                    raise
                time.sleep(2 ** attempt)

class Crew:
    def __init__(self, agents: list[Agent], tasks: list[Task], process: ProcessType = ProcessType.SEQUENTIAL):
        self.agents = {a.config.name: a for a in agents}
        self.tasks = tasks
        self.process = process
        self.log = logging.getLogger("crew")

    def kickoff(self) -> list[Task]:
        self.log.info(f"Kickoff {len(self.tasks)} tasks ({self.process.value})")
        if self.process == ProcessType.SEQUENTIAL:
            return self._run_sequential()
        elif self.process == ProcessType.PARALLEL:
            return self._run_parallel()
        elif self.process == ProcessType.HIERARCHICAL:
            return self._run_hierarchical()

    def _run_sequential(self) -> list[Task]:
        results = {}
        for task in self.tasks:
            agent = self.agents.get(task.agent or list(self.agents.keys())[0])
            if not agent:
                raise ValueError(f"Agent '{task.agent}' not found")
            # inject prior results into context
            task.context["_prior_results"] = {k: v for k, v in results.items()}
            task.result = agent.run(task)
            results[task.id or task.description] = task.result
            if task.callback:
                task.callback(task)
        return self.tasks

    def _run_parallel(self) -> list[Task]:
        from concurrent.futures import ThreadPoolExecutor
        def _exec(t):
            agent = self.agents.get(t.agent or list(self.agents.keys())[0])
            t.result = agent.run(t)
            return t
        with ThreadPoolExecutor(max_workers=len(self.tasks)) as ex:
            return list(ex.map(_exec, self.tasks))

    def _run_hierarchical(self) -> list[Task]:
        manager = self.agents.get("manager") or next(iter(self.agents.values()))
        completed = []
        for task in self.tasks:
            result = manager.run(task)
            task.result = result
            completed.append(task)
        return completed

    def summary(self) -> str:
        lines = []
        for t in self.tasks:
            status = "done" if t.result else "pending"
            agent = t.agent or "auto"
            lines.append(f"  [{status}] {t.id or 'task'} -> {agent}: {str(t.result)[:80]}")
        return "\n".join(lines)

# === OCR-specific agents ===
class OCRAgent(Agent):
    """Agent specialised for OCR/document parsing using configurable endpoints."""
    def _call_api(self, task: Task) -> str:
        image_path = task.context.get("image_path", "")
        pdf_path = task.context.get("pdf_path", "")

        if self.config.endpoint and "openai" in self.config.endpoint.lower():
            return self._openai_vision(task, image_path or pdf_path)
        elif self.config.endpoint:
            return self._generic_ocr(task)
        return self._local_fn(task)

    def _openai_vision(self, task: Task, file_path: str) -> str:
        import base64
        headers = {"Content-Type": "application/json", **self.config.auth_headers()}
        image_data = None
        if file_path and os.path.exists(file_path):
            with open(file_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode()
        payload = {
            "model": self.config.model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": task.description},
                    *([{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}"}}] if image_data else [])
                ]
            }],
            "max_tokens": self.config.max_tokens,
        }
        r = requests.post(self.config.endpoint_url("v1/chat/completions"), json=payload, headers=headers, timeout=self.config.timeout)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    def _generic_ocr(self, task: Task) -> str:
        url = self.config.endpoint_url("v1/chat/completions")
        headers = {"Content-Type": "application/json", **self.config.auth_headers()}
        image_path = task.context.get("image_path", "")
        image_data = None
        if image_path and os.path.exists(image_path):
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode()
        payload = {
            "model": self.config.model,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": task.description},
                *([{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}"}}] if image_data else [])
            ]}],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        r = requests.post(url, json=payload, headers=headers, timeout=self.config.timeout)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

class DocumentAnalyzer(Agent):
    """Analyzes parsed document content from OCR."""
    pass

class QualityChecker(Agent):
    """Validates OCR output quality and flags issues."""
    pass
