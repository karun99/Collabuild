"""Collabuild MAS — Multi-Agent System for Research Paper → Production Pipeline."""

__version__ = "1.0.0"

from . import devsrs, reach
from .devsrs import DevSRS, SRSBlueprint, parse_srs
from .mas import Agent, AgentConfig, AuthType, Crew, ProcessType, Task
from .pipeline import CollabuildPipeline, StageResult
from .providers import (
    BhashiniAIProvider,
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
    "BhashiniAIProvider", "ClaudeProvider", "DevProvider", "KoboldCPPProvider", "LLMProvider",
    "NvidiaProvider", "OllamaProvider", "OpenAICompatibleProvider",
    "OpenRouterProvider", "TextGenWebUIProvider",
    "create_provider", "discover_local_models",
    "DevSRS", "SRSBlueprint", "parse_srs",
    "reach", "devsrs",
]
