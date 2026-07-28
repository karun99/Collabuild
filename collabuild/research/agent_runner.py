"""Agent Runner — autonomous research agent with tool use.

Pattern: inspired by GitHub Agentic Workflows (gh-aw) and ai-agent-runner.
Runs a research loop:
  1. User provides a task/query
  2. Agent breaks it into sub-steps
  3. Agent uses tools (web fetch, OCR, code exec) to gather data
  4. Agent synthesizes findings with LLM
  5. Returns structured research output

Tools available:
  • web_fetch   — fetch and extract text from URLs
  • ocr_file    — OCR a document/image via Baidu
  • ocr_image   — OCR an image via Baidu
  • python_exec — execute Python code (sandboxed)
  • search      — web search (placeholder for integration)

All tool calls go through the agent runner — no raw LLM tool calls.
"""

import json
import logging
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field

log = logging.getLogger("research.agent")


@dataclass
class ToolCall:
    """Record of a single tool invocation."""
    tool: str
    args: dict
    result: str
    success: bool
    duration_ms: float = 0.0
    error: str = ""


@dataclass
class AgentStep:
    """Single step in the agent's reasoning loop."""
    step_num: int
    thought: str
    tool_calls: list = field(default_factory=list)
    output: str = ""


@dataclass
class AgentResult:
    """Final result of an agent run."""
    task: str
    steps: list = field(default_factory=list)
    final_answer: str = ""
    total_tool_calls: int = 0
    total_duration_ms: float = 0.0
    success: bool = True
    error: str = ""


class AgentRunner:
    """Autonomous research agent that uses LLM + tools to complete tasks.

    Args:
        llm_chat: callable(model, messages, temperature, max_tokens) → str
        llm_model: model name to use
        web_fetcher: WebFetcher instance (optional)
        ocr_client: BaiduOCR instance (optional)
        max_steps: max reasoning steps before forced termination
        max_tool_calls: max total tool calls
        timeout: total timeout in seconds
        temperature: LLM temperature for reasoning
    """

    SYSTEM_PROMPT = """You are a research agent. You help users gather information, analyze data, and produce comprehensive research outputs.

You have access to these tools:
- web_fetch: Fetch a URL and extract its text content. Args: {url: string}
- ocr_file: OCR a local document file (PDF, image, etc.) via Baidu OCR. Args: {file_path: string}
- ocr_image: OCR a local image file via Baidu OCR. Args: {file_path: string}
- python_exec: Execute Python code in a sandbox. Args: {code: string}
- search: Search the web for information. Args: {query: string}

For each step, respond with JSON:
{
  "thought": "your reasoning about what to do next",
  "tool_calls": [{"tool": "tool_name", "args": {...}}],
  "output": "interim output or empty string"
}

When you have gathered enough information and are ready to provide the final answer,
set "output" to your comprehensive final answer and leave "tool_calls" as an empty list.

Always be thorough. Check multiple sources when possible. Cite your sources."""

    def __init__(self, llm_chat: Callable = None, llm_model: str = "default",
                 web_fetcher=None, ocr_client=None,
                 max_steps: int = 15, max_tool_calls: int = 50,
                 timeout: int = 600, temperature: float = 0.3):
        self.llm_chat = llm_chat or self._dummy_chat
        self.llm_model = llm_model
        self.web_fetcher = web_fetcher
        self.ocr_client = ocr_client
        self.max_steps = max_steps
        self.max_tool_calls = max_tool_calls
        self.timeout = timeout
        self.temperature = temperature

    def _dummy_chat(self, model, messages, temperature=0.3, max_tokens=4096):
        return '{"thought":"No LLM configured. Returning task as-is.","tool_calls":[],"output":"Task requires LLM configuration. Please set up a provider in settings."}'

    def run(self, task: str, context: str = "") -> AgentResult:
        """Execute a research task. Returns AgentResult with steps and final answer."""
        start = time.time()
        result = AgentResult(task=task)
        messages = []
        total_tool_calls = 0

        system = self.SYSTEM_PROMPT
        if context:
            system += f"\n\nAdditional context:\n{context}"
        messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": task})

        log.info("[agent] starting task: %s", task[:100])

        for step_num in range(1, self.max_steps + 1):
            if time.time() - start > self.timeout:
                result.error = f"Timeout after {self.timeout}s"
                break
            if total_tool_calls >= self.max_tool_calls:
                result.error = f"Max tool calls ({self.max_tool_calls}) reached"
                break

            # Get LLM response
            try:
                raw = self.llm_chat(self.llm_model, messages, self.temperature, 4096)
            except Exception as e:
                log.error("[agent] LLM call failed at step %d: %s", step_num, e)
                result.error = f"LLM error at step {step_num}: {e}"
                result.success = False
                break

            # Parse response
            parsed = self._parse_response(raw)
            step = AgentStep(
                step_num=step_num,
                thought=parsed.get("thought", ""),
                output=parsed.get("output", ""),
            )

            # Execute tool calls
            tool_calls = parsed.get("tool_calls", [])
            for tc in tool_calls:
                if total_tool_calls >= self.max_tool_calls:
                    break
                tool_name = tc.get("tool", "")
                tool_args = tc.get("args", {})
                t0 = time.time()
                try:
                    tool_result = self._execute_tool(tool_name, tool_args)
                    success = True
                    error = ""
                except Exception as e:
                    tool_result = f"[Tool error: {e}]"
                    success = False
                    error = str(e)
                dur = (time.time() - t0) * 1000
                step.tool_calls.append(ToolCall(
                    tool=tool_name, args=tool_args, result=tool_result,
                    success=success, duration_ms=dur, error=error,
                ))
                total_tool_calls += 1

            result.steps.append(step)

            # Build assistant response for next turn
            assistant_msg = json.dumps({
                "thought": step.thought,
                "tool_calls": [{"tool": tc.tool, "args": tc.args, "result": tc.result[:2000]}
                               for tc in step.tool_calls],
                "output": step.output,
            })
            messages.append({"role": "assistant", "content": assistant_msg})

            # Add tool results as user message
            if step.tool_calls:
                results_text = "\n\n".join(
                    f"[{tc.tool}] result:\n{tc.result[:3000]}" for tc in step.tool_calls
                )
                messages.append({"role": "user", "content": f"Tool results:\n{results_text}"})

            # Check if agent is done (no tool calls, has output)
            if not step.tool_calls and step.output:
                result.final_answer = step.output
                break

        # If no final answer, synthesize from steps
        if not result.final_answer and result.steps:
            try:
                synthesize_prompt = "Based on the research steps above, provide a comprehensive final answer to the original task. Synthesize all findings into a clear, well-structured response."
                messages.append({"role": "user", "content": synthesize_prompt})
                result.final_answer = self.llm_chat(self.llm_model, messages, self.temperature, 4096)
            except Exception:
                result.final_answer = "\n\n".join(
                    s.output for s in result.steps if s.output
                ) or "Research completed but no final synthesis available."

        result.total_tool_calls = total_tool_calls
        result.total_duration_ms = (time.time() - start) * 1000
        log.info("[agent] task completed: %d steps, %d tool calls, %.1fs",
                 len(result.steps), total_tool_calls, result.total_duration_ms / 1000)
        return result

    def _parse_response(self, raw: str) -> dict:
        """Parse LLM response as JSON, falling back to text extraction."""
        raw = raw.strip()
        # Try direct JSON parse
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        # Try extracting JSON from markdown code block
        import re
        match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        # Fallback: treat entire response as final output
        return {"thought": "Non-JSON response", "tool_calls": [], "output": raw}

    def _execute_tool(self, tool_name: str, args: dict) -> str:
        """Route tool call to the appropriate handler."""
        if tool_name == "web_fetch":
            return self._tool_web_fetch(args)
        elif tool_name == "ocr_file":
            return self._tool_ocr_file(args)
        elif tool_name == "ocr_image":
            return self._tool_ocr_image(args)
        elif tool_name == "python_exec":
            return self._tool_python_exec(args)
        elif tool_name == "search":
            return self._tool_search(args)
        else:
            return f"[Unknown tool: {tool_name}. Available: web_fetch, ocr_file, ocr_image, python_exec, search]"

    def _tool_web_fetch(self, args: dict) -> str:
        url = args.get("url", "")
        if not url:
            return "[Error: url parameter required]"
        if not self.web_fetcher:
            return "[Error: WebFetcher not configured]"
        result = self.web_fetcher.fetch_url(url)
        text = result.get("text", "")
        title = result.get("title", "")
        words = result.get("word_count", 0)
        return f"Title: {title}\nWords: {words}\n\n{text[:8000]}"

    def _tool_ocr_file(self, args: dict) -> str:
        file_path = args.get("file_path", "")
        if not file_path:
            return "[Error: file_path parameter required]"
        if not self.ocr_client:
            return "[Error: BaiduOCR not configured]"
        return self.ocr_client.parse_document(file_path)

    def _tool_ocr_image(self, args: dict) -> str:
        file_path = args.get("file_path", "")
        if not file_path:
            return "[Error: file_path parameter required]"
        if not self.ocr_client:
            return "[Error: BaiduOCR not configured]"
        with open(file_path, "rb") as f:
            data = f.read()
        lines = self.ocr_client.ocr_general(data)
        return "\n".join(lines)

    def _tool_python_exec(self, args: dict) -> str:
        code = args.get("code", "")
        if not code:
            return "[Error: code parameter required]"
        # Sandboxed exec — limited builtins
        import contextlib
        import io
        stdout = io.StringIO()
        stderr = io.StringIO()
        safe_builtins = {
            "print": print, "len": len, "range": range, "str": str,
            "int": int, "float": float, "list": list, "dict": dict,
            "tuple": tuple, "set": set, "bool": bool, "True": True,
            "False": False, "None": None, "abs": abs, "min": min,
            "max": max, "sum": sum, "sorted": sorted, "enumerate": enumerate,
            "zip": zip, "map": map, "filter": filter, "isinstance": isinstance,
            "type": type, "hasattr": hasattr, "getattr": getattr,
            "Exception": Exception, "ValueError": ValueError,
            "TypeError": TypeError, "KeyError": KeyError,
        }
        namespace = {"__builtins__": safe_builtins}
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exec(code, namespace)
        except Exception as e:
            return f"Error: {e}\n{traceback.format_exc()}"
        out = stdout.getvalue()
        err = stderr.getvalue()
        result = out
        if err:
            result += f"\n[stderr]\n{err}"
        return result[:8000] or "[exec completed, no output]"

    def _tool_search(self, args: dict) -> str:
        """Search tool — placeholder that returns guidance."""
        query = args.get("query", "")
        return (f"[Search for: {query}]\n"
                "Search tool is a placeholder. Use web_fetch with specific URLs instead.\n"
                "To search, provide direct URLs to fetch and analyze.")

    def status(self) -> dict:
        return {
            "provider": "agent_runner",
            "max_steps": self.max_steps,
            "max_tool_calls": self.max_tool_calls,
            "timeout": self.timeout,
            "has_llm": self.llm_chat != self._dummy_chat,
            "has_web_fetcher": self.web_fetcher is not None,
            "has_ocr": self.ocr_client is not None,
            "tools": ["web_fetch", "ocr_file", "ocr_image", "python_exec", "search"],
        }
