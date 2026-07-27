"""Tests for collabuild.config — YAML loading and env var resolution."""

import os
import pytest
import tempfile
import yaml
from collabuild.config import load, get_provider_config, get_pipeline_config


class TestLoad:
    def test_load_bundled_config(self):
        cfg = load()
        assert isinstance(cfg, dict)
        assert "providers" in cfg

    def test_load_custom_path(self, tmp_path):
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text("providers:\n  test:\n    endpoint: http://test\n")
        cfg = load(str(config_file))
        assert "providers" in cfg
        assert "test" in cfg["providers"]

    def test_load_missing_file_returns_defaults(self, tmp_path):
        cfg = load(str(tmp_path / "nonexistent.yaml"))
        assert cfg == {}

    def test_load_invalid_yaml_returns_defaults(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text(": invalid: yaml: {{{{")
        cfg = load(str(bad))
        assert cfg == {}


class TestEnvResolution:
    def test_env_var_substitution(self, monkeypatch, tmp_path):
        monkeypatch.setenv("TEST_API_KEY", "sk-test-12345")
        config_file = tmp_path / "env_test.yaml"
        config_file.write_text("providers:\n  test:\n    api_key: \"${TEST_API_KEY}\"\n")
        cfg = load(str(config_file))
        assert cfg["providers"]["test"]["api_key"] == "sk-test-12345"

    def test_missing_env_var_becomes_empty(self, tmp_path):
        config_file = tmp_path / "env_missing.yaml"
        config_file.write_text("providers:\n  test:\n    api_key: \"${NONEXISTENT_VAR_12345}\"\n")
        cfg = load(str(config_file))
        assert cfg["providers"]["test"]["api_key"] == ""

    def test_multiple_env_vars(self, monkeypatch, tmp_path):
        monkeypatch.setenv("VAR_A", "alpha")
        monkeypatch.setenv("VAR_B", "beta")
        config_file = tmp_path / "multi_env.yaml"
        config_file.write_text('key: "${VAR_A}-${VAR_B}"\n')
        cfg = load(str(config_file))
        assert cfg["key"] == "alpha-beta"

    def test_non_env_var_strings_unchanged(self, tmp_path):
        config_file = tmp_path / "plain.yaml"
        config_file.write_text('key: "plain value"\n')
        cfg = load(str(config_file))
        assert cfg["key"] == "plain value"


class TestGetProviderConfig:
    def test_default_provider(self):
        cfg = {"providers": {"openrouter": {"endpoint": "https://test"}}}
        result = get_provider_config(cfg)
        assert result["provider"] == "openrouter"

    def test_custom_provider(self):
        cfg = {"providers": {"ollama": {"endpoint": "http://localhost:11434"}}}
        result = get_provider_config(cfg, "ollama")
        assert result["provider"] == "ollama"
        assert result["endpoint"] == "http://localhost:11434"

    def test_missing_provider_returns_empty(self):
        cfg = {"providers": {}}
        result = get_provider_config(cfg, "nonexistent")
        assert result["provider"] == "nonexistent"

    def test_pipeline_provider_override(self):
        cfg = {
            "pipeline": {"provider": "nvidia"},
            "providers": {"nvidia": {"endpoint": "https://nvidia.test"}},
        }
        result = get_provider_config(cfg)
        assert result["provider"] == "nvidia"


class TestGetPipelineConfig:
    def test_returns_pipeline_section(self):
        cfg = {"pipeline": {"provider": "openrouter", "stages": {}}}
        result = get_pipeline_config(cfg)
        assert result["provider"] == "openrouter"

    def test_missing_pipeline_returns_empty(self):
        result = get_pipeline_config({})
        assert result == {}
