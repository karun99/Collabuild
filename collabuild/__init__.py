"""Collabuild MAS — Multi-Agent System for Research Paper → Production Pipeline."""

__version__ = "0.3.0"

from .pipeline import CollabuildPipeline, StageResult
from .mas import Agent, Crew, Task, AgentConfig, AuthType, ProcessType
from .providers import (
    create_provider, discover_local_models, LLMProvider,
    OpenRouterProvider, NvidiaProvider, OllamaProvider, KoboldCPPProvider,
    TextGenWebUIProvider, ClaudeProvider, OpenAICompatibleProvider, DevProvider,
)
