"""Tests for collabuild.pipeline — DevProvider-powered pipeline."""

from collabuild.pipeline import CollabuildPipeline, StageAgent, StageResult
from collabuild.providers import DevProvider


class TestStageResult:
    def test_defaults(self):
        r = StageResult(stage="test", agent="agent", content="hello")
        assert r.passed is True
        assert r.mermaid == ""
        assert r.artifacts == {}

    def test_failed_result(self):
        r = StageResult(stage="test", agent="agent", content="error", passed=False)
        assert r.passed is False


class TestStageAgent:
    def test_no_provider_returns_skip_message(self):
        agent = StageAgent("test", "tester", provider=None)
        result = agent.call("system", "user")
        assert "No provider configured" in result

    def test_dev_provider_returns_content(self):
        agent = StageAgent("test", "tester", provider=DevProvider(), model="dev-model")
        result = agent.call("system", "user")
        assert len(result) > 0
        assert isinstance(result, str)

    def test_last_error_tracking(self):
        agent = StageAgent("test", "tester", provider=None)
        agent.call("system", "user")
        assert agent._last_error is not None

    def test_extract_mermaid_from_code_block(self):
        agent = StageAgent("test", "tester", provider=DevProvider())
        text = "Some text\n\n```mermaid\nflowchart TD\n    A-->B\n```\n\nMore text"
        mermaid = agent.extract_mermaid(text)
        assert "flowchart" in mermaid

    def test_extract_mermaid_returns_empty_when_none(self):
        agent = StageAgent("test", "tester", provider=DevProvider())
        mermaid = agent.extract_mermaid("No mermaid here")
        assert mermaid == ""


class TestDevPipeline:
    def test_pipeline_creation(self, dev_pipeline):
        assert dev_pipeline.provider is not None
        assert isinstance(dev_pipeline.provider, DevProvider)
        assert len(dev_pipeline.stages) == 9

    def test_pipeline_stages_all_have_provider(self, dev_pipeline):
        for name, stage in dev_pipeline.stages.items():
            assert stage.provider is not None, f"Stage {name} has no provider"

    def test_full_pipeline_run(self, dev_pipeline):
        results = dev_pipeline.run("Test paper text about OCR systems.")
        assert len(results) == 9
        assert all(isinstance(r, StageResult) for r in results.values())

    def test_pipeline_results_all_pass_with_dev(self, dev_pipeline):
        results = dev_pipeline.run("Test paper.")
        for name, r in results.items():
            assert r.passed, f"Stage {name} failed with DevProvider"

    def test_pipeline_generates_mermaid_diagrams(self, dev_pipeline):
        results = dev_pipeline.run("Test paper.")
        mermaid_count = sum(1 for r in results.values() if r.mermaid)
        assert mermaid_count >= 5, f"Expected at least 5 mermaid diagrams, got {mermaid_count}"

    def test_pipeline_report_generation(self, dev_pipeline):
        dev_pipeline.run("Test paper.")
        report = dev_pipeline.report()
        assert "Collabuild MAS" in report
        assert "Paper Analysis" in report
        assert "Final Review" in report
        assert "PASS" in report

    def test_pipeline_report_contains_all_stages(self, dev_pipeline):
        dev_pipeline.run("Test paper.")
        report = dev_pipeline.report()
        expected_stages = [
            "Paper Analysis", "SRS Generation", "Module Design",
            "User Flow Design", "SDLC Plan", "Code Generation",
            "Debugging & Review", "Deployment Plan", "Final Review",
        ]
        for stage in expected_stages:
            assert stage in report, f"Missing stage in report: {stage}"


class TestFromConfig:
    def test_from_config_with_dev(self, tmp_path):
        import yaml
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({
            "pipeline": {"provider": "dev"},
            "providers": {"dev": {}},
        }))
        pipeline = CollabuildPipeline.from_config(str(config_file))
        assert isinstance(pipeline.provider, DevProvider)
