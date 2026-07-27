"""Configuration loader for Collabuild MAS.

Loads config.yaml from the package directory (or a custom path),
merges with environment variables, and provides typed access.
"""

import os, re, logging
from typing import Any

log = logging.getLogger("config")

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")

_ENV_PATTERN = re.compile(r'\$\{(\w+)\}')


def _substitute_env(s: str) -> str:
    def _replace(m):
        val = os.getenv(m.group(1), "")
        if not val:
            log.debug("Env var %s not set, using empty string", m.group(1))
        return val
    return _ENV_PATTERN.sub(_replace, s)


def _resolve_env(obj: Any) -> None:
    """Recursively resolve ${ENV_VAR} placeholders in config dict/list."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and "${" in v:
                obj[k] = _substitute_env(v)
            else:
                _resolve_env(v)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            if isinstance(v, str) and "${" in v:
                obj[i] = _substitute_env(v)
            else:
                _resolve_env(v)


def load(path: str = "") -> dict:
    """Load config.yaml from the given path (default: bundled config).

    Environment variables in ${VAR_NAME} format are resolved automatically.
    """
    path = path or CONFIG_PATH
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except FileNotFoundError:
        log.warning("Config not found at %s, using defaults", path)
        cfg = {}
    except Exception as e:
        log.warning("Failed to load config: %s, using defaults", e)
        cfg = {}

    _resolve_env(cfg)
    return cfg


def get_provider_config(cfg: dict, provider_name: str = "") -> dict:
    """Get the active provider configuration.

    Returns a dict with keys: provider, api_key, endpoint, model.
    """
    pipeline_cfg = cfg.get("pipeline", {})
    provider_name = provider_name or pipeline_cfg.get("provider", "openrouter")
    providers = cfg.get("providers", {})
    provider_cfg = dict(providers.get(provider_name, {}))
    provider_cfg.setdefault("provider", provider_name)

    # Resolve any remaining ${ENV_VAR} in api_key
    api_key = provider_cfg.get("api_key", "")
    if isinstance(api_key, str) and "${" in api_key:
        provider_cfg["api_key"] = _substitute_env(api_key)

    return provider_cfg


def get_ai_config(cfg: dict, provider_name: str = "") -> dict:
    """Return a flat, simple AI config dict: {provider, api_key, endpoint, model}.

    This is the single entry point for building provider configs.
    Merges: config.yaml provider defaults + pipeline.provider + chat defaults.
    """
    provider_cfg = get_provider_config(cfg, provider_name)
    chat_cfg = cfg.get("chat", {})

    return {
        "provider": provider_cfg.get("provider", "openrouter"),
        "api_key": provider_cfg.get("api_key", ""),
        "endpoint": provider_cfg.get("endpoint", ""),
        "model": provider_cfg.get("model", ""),
        "temperature": chat_cfg.get("temperature", 0.7),
        "max_tokens": chat_cfg.get("max_tokens", 4096),
    }


def get_stage_config(cfg: dict, stage_name: str) -> dict:
    """Get per-stage config (temperature, max_tokens) from config.yaml pipeline.stages."""
    stages = cfg.get("pipeline", {}).get("stages", {})
    return stages.get(stage_name, {})


def get_pipeline_config(cfg: dict) -> dict:
    """Get pipeline-level configuration (output, stages)."""
    return cfg.get("pipeline", {})
