# Contributing to Collabuild MAS

Thank you for your interest in contributing! This guide will help you get started.

## Development Setup

### Prerequisites

- Python 3.10 or higher
- Git
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/karun99/Collabuild.git
cd Collabuild

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install in editable mode with all extras
pip install -e ".[web,dev,all]"
```

### Verify Installation

```bash
# Run tests
pytest tests/ -v

# Lint
ruff check collabuild/

# Run in dev mode (no API key needed)
collabuild --dev
```

## Project Structure

```
Collabuild/
├── collabuild/
│   ├── __init__.py          # Package exports
│   ├── __main__.py          # CLI entry point
│   ├── config.py            # YAML config + env var resolution
│   ├── providers.py         # LLM providers (8+: OpenRouter, NVIDIA, Claude, Ollama, KoboldCPP, textgen, Bhashini AI, Dev)
│   ├── mas.py               # Multi-Agent System (Agent, Crew, Task, AgentRunnerAgent)
│   ├── pipeline.py          # 9-stage research pipeline
│   ├── ocr/                 # Baidu OCR integration + agent-runner factory
│   ├── research/            # Web fetcher + agent runner
│   └── web/                 # FastAPI web UI
│       ├── app.py
│       └── templates/
├── tests/                   # Test suite
├── pyproject.toml           # Project metadata + build config
├── config.yaml              # Default configuration
└── UML.md                   # Architecture diagrams
```

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Make Changes

- Follow the existing code style
- Add tests for new functionality
- Update documentation if needed

### 3. Lint and Test

```bash
# Lint
ruff check collabuild/

# Auto-fix lint issues
ruff check collabuild/ --fix

# Format
ruff format collabuild/

# Run tests
pytest tests/ -v
```

### 4. Commit

```bash
git add .
git commit -m "feat: add your feature description"
```

Use [Conventional Commits](https://www.conventionalcommits.org/) format:
- `feat:` — New feature
- `fix:` — Bug fix
- `docs:` — Documentation changes
- `test:` — Adding tests
- `refactor:` — Code refactoring
- `chore:` — Maintenance tasks

### 5. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub.

## Adding a New LLM Provider

*For reference, see the `BhashiniAIProvider` implementation in `collabuild/providers.py:1077` as a complete example of a non-OpenAI provider with translation, TTS, and custom pipeline APIs.*

1. In `collabuild/providers.py`, create a new class inheriting from `LLMProvider` or `OpenAICompatibleProvider`:

```python
class MyProvider(LLMProvider):
    def __init__(self, api_key: str = "", endpoint: str = "", name: str = "myprovider"):
        super().__init__(name)
        self.endpoint = endpoint
        self.api_key = api_key

    def chat(self, model: str, messages: list, temperature: float = 0.3,
             max_tokens: int = 4096) -> str:
        # Implement API call
        ...

    def chat_stream(self, model: str, messages: list, temperature: float = 0.3,
                    max_tokens: int = 4096) -> Iterator[str]:
        # Implement streaming
        ...

    def list_models(self) -> list:
        # Return available models
        ...
```

2. Register in `PROVIDER_REGISTRY`:

```python
PROVIDER_REGISTRY = {
    ...
    "myprovider": MyProvider,
}
```

3. Add config in `config.yaml`:

```yaml
providers:
  myprovider:
    endpoint: "https://api.myprovider.com/v1"
    api_key: "${MYPROVIDER_API_KEY}"
    model: "default-model"
```

4. Add tests in `tests/test_providers.py`.

## Adding a Pipeline Stage

1. Create a new class in `collabuild/pipeline.py` inheriting from `StageAgent`:

```python
class MyStage(StageAgent):
    def run(self, previous_result: str) -> StageResult:
        sys = "System prompt for this stage"
        usr = f"User prompt using: {previous_result[:6000]}"
        content = self.call(sys, usr)
        mermaid = self.extract_mermaid(content)
        return StageResult(
            stage="My Stage",
            agent=self.name,
            content=content,
            mermaid=mermaid,
            passed=self._last_error is None,
        )
```

2. Register in `CollabuildPipeline.__init__`.

## Code Style

- Python 3.10+ syntax
- Line length: 120 characters max
- Use type hints
- Follow existing patterns in the codebase
- No comments unless asked

## Reporting Issues

Open an issue on [GitHub Issues](https://github.com/karun99/Collabuild/issues) with:

- Description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Python version and OS

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
