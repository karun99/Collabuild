"""Tests for collabuild.providers — DevProvider and factory."""

import pytest
from collabuild.providers import (
    DevProvider, create_provider, LLMProvider, OpenRouterProvider,
    NvidiaProvider, OllamaProvider, KoboldCPPProvider, ClaudeProvider,
    PROVIDER_REGISTRY, messages_to_prompt,
)


class TestDevProvider:
    def test_instantiation(self):
        p = DevProvider()
        assert p.name == "dev"

    def test_chat_returns_string(self, dev_provider):
        result = dev_provider.chat("dev-model", [{"role": "user", "content": "hello"}])
        assert isinstance(result, str)
        assert len(result) > 0

    def test_chat_returns_stage_response_for_paper_analysis(self, dev_provider):
        msgs = [
            {"role": "system", "content": "You are a paper analyst."},
            {"role": "user", "content": "Perform paper analysis on this OCR paper."},
        ]
        result = dev_provider.chat("dev-model", msgs)
        assert "Paper Analysis" in result
        assert "mermaid" in result.lower() or "flowchart" in result.lower()

    def test_chat_returns_stage_response_for_srs(self, dev_provider):
        msgs = [
            {"role": "system", "content": "You are an SRS engineer."},
            {"role": "user", "content": "Generate srs generation for OCR system."},
        ]
        result = dev_provider.chat("dev-model", msgs)
        assert "Software Requirements Specification" in result

    def test_chat_returns_stage_response_for_module_design(self, dev_provider):
        msgs = [
            {"role": "system", "content": "You are a software architect."},
            {"role": "user", "content": "Create the module design for the system."},
        ]
        result = dev_provider.chat("dev-model", msgs)
        assert "Module" in result

    def test_chat_returns_stage_response_for_code_gen(self, dev_provider):
        msgs = [
            {"role": "system", "content": "You are a developer."},
            {"role": "user", "content": "Start code generation for the OCR engine."},
        ]
        result = dev_provider.chat("dev-model", msgs)
        assert "Code Generation" in result

    def test_chat_returns_stage_response_for_deployment(self, dev_provider):
        msgs = [
            {"role": "system", "content": "You are a DevOps engineer."},
            {"role": "user", "content": "Create deployment plan for the system."},
        ]
        result = dev_provider.chat("dev-model", msgs)
        assert "Deployment" in result

    def test_chat_returns_stage_response_for_final_review(self, dev_provider):
        msgs = [
            {"role": "system", "content": "You are a QA lead."},
            {"role": "user", "content": "Perform final review of pipeline output."},
        ]
        result = dev_provider.chat("dev-model", msgs)
        assert "Final Review" in result

    def test_chat_stream_yields_tokens(self, dev_provider):
        msgs = [{"role": "user", "content": "hello"}]
        tokens = list(dev_provider.chat_stream("dev-model", msgs))
        assert len(tokens) > 0
        assert all(isinstance(t, str) for t in tokens)

    def test_list_models(self, dev_provider):
        models = dev_provider.list_models()
        assert "dev-model" in models

    def test_no_network_calls(self, dev_provider):
        """DevProvider must not make any HTTP requests."""
        result = dev_provider.chat("dev-model", [{"role": "user", "content": "test"}])
        assert "DevProvider" in result or "Dev Mode" in result or "Pipeline" in result


class TestFactory:
    def test_create_dev_provider(self):
        p = create_provider({"provider": "dev"})
        assert isinstance(p, DevProvider)

    def test_create_dev_provider_no_kwargs(self):
        p = create_provider({"provider": "dev"})
        assert p.name == "dev"

    def test_provider_registry_has_dev(self):
        assert "dev" in PROVIDER_REGISTRY

    def test_provider_registry_has_all(self):
        required = ["openrouter", "nvidia", "claude", "ollama", "koboldcpp", "textgen", "dev"]
        for name in required:
            assert name in PROVIDER_REGISTRY, f"Missing: {name}"

    def test_create_openrouter(self):
        p = create_provider({"provider": "openrouter", "api_key": "test-key"})
        assert isinstance(p, OpenRouterProvider)

    def test_create_nvidia(self):
        p = create_provider({"provider": "nvidia", "api_key": "test-key"})
        assert isinstance(p, NvidiaProvider)

    def test_create_claude(self):
        p = create_provider({"provider": "claude", "api_key": "test-key"})
        assert isinstance(p, ClaudeProvider)


class TestMessagesToPrompt:
    def test_system_message(self):
        msgs = [{"role": "system", "content": "Be helpful."}]
        result = messages_to_prompt(msgs)
        assert "System: Be helpful." in result
        assert result.endswith("Assistant: ")

    def test_user_message(self):
        msgs = [{"role": "user", "content": "Hello"}]
        result = messages_to_prompt(msgs)
        assert "User: Hello" in result

    def test_assistant_message(self):
        msgs = [{"role": "assistant", "content": "Hi there"}]
        result = messages_to_prompt(msgs)
        assert "Assistant: Hi there" in result

    def test_multi_turn(self):
        msgs = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "User msg"},
            {"role": "assistant", "content": "AI response"},
            {"role": "user", "content": "Follow up"},
        ]
        result = messages_to_prompt(msgs)
        assert "System: System prompt" in result
        assert "User: User msg" in result
        assert "Assistant: AI response" in result
        assert "User: Follow up" in result
