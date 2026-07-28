"""Collabuild MAS — Multi-Agent System for Research Paper → Production Pipeline."""

__version__ = "0.3.0"

from .mas import Agent, AgentConfig, AuthType, Crew, ProcessType, Task
from .pipeline import CollabuildPipeline, StageResult
from .providers import (
    ClaudeProvider,
    DevProvider,
    KoboldCPPProvider,
    LLMProvider,
    NvidiaProvider,
    OllamaProvider,
    OpenAICompatibleProvider,
    OpenRouterProvider,
    TextGenWebUIProvider,
    create_provider,
    discover_local_models,
)

__all__ = [
    "Agent", "AgentConfig", "AuthType", "Crew", "ProcessType", "Task",
    "CollabuildPipeline", "StageResult",
    "ClaudeProvider", "DevProvider", "KoboldCPPProvider", "LLMProvider",
    "NvidiaProvider", "OllamaProvider", "OpenAICompatibleProvider",
    "OpenRouterProvider", "TextGenWebUIProvider",
    "create_provider", "discover_local_models",
]
