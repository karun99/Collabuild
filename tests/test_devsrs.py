"""Tests for collabuild.devsrs — SRS-to-application builder."""

import subprocess
import sys

from collabuild.devsrs import DevSRS, SRSBlueprint, parse_srs
from collabuild.providers import DevProvider


class TestParseSRS:
    def test_parse_srs_extracts_overview(self):
        srs = "# Software Requirements Specification\n## 1. Introduction\n### 1.1 Purpose\nDoc parser app.\n## 3. Functional Requirements\n### 3.1 Upload Module\nUpload files."
        blueprint = parse_srs(srs)
        assert isinstance(blueprint, SRSBlueprint)
        assert len(blueprint.modules) >= 1

    def test_parse_srs_returns_modules_and_name(self):
        srs = (
            "# Software Requirements Specification\n"
            "## 1. Introduction\n### 1.1 Purpose\nOCR App\n"
            "## 3. Functional Requirements\n"
            "- FR-1 The system shall accept a document upload.\n"
            "- FR-2 The system shall run OCR on the uploaded document.\n"
            "## 4. System Features\n"
            "- Document Upload\n"
            "- OCR Engine\n"
        )
        blueprint = parse_srs(srs)
        assert isinstance(blueprint.modules, list)
        assert any("Upload" in m for m in blueprint.modules)
        assert any("OCR" in m for m in blueprint.modules)

    def test_parse_srs_empty_document(self):
        blueprint = parse_srs("")
        assert isinstance(blueprint.modules, list)
        assert blueprint.title == "Generated Application"


class TestDevSRS:
    def _build(self, target, tmp_path, provider=None):
        srs = DevProvider().STAGE_RESPONSES["srs generation"]
        builder = DevSRS(provider=provider or DevProvider(), target=target, output_dir=str(tmp_path))
        return builder.build(srs, use_llm=False)

    def test_build_cli(self, tmp_path):
        build = self._build("cli", tmp_path)
        assert build["target"] == "cli"
        assert build["smoke_ok"] is True
        assert "main.py" in build["files"]
        assert (tmp_path / "main.py").exists()
        assert (tmp_path / "requirements.txt").exists()

    def test_build_web(self, tmp_path):
        build = self._build("web", tmp_path)
        assert build["target"] == "web"
        assert build["smoke_ok"] is True
        assert "main.py" in build["files"]
        assert "static/index.html" in build["files"]

    def test_build_mcp(self, tmp_path):
        build = self._build("mcp", tmp_path)
        assert build["target"] == "mcp"
        assert build["smoke_ok"] is True
        assert "server.py" in build["files"]

    def test_all_generated_python_compiles(self, tmp_path):
        for target in ("cli", "web", "mcp"):
            out = tmp_path / target
            out.mkdir(exist_ok=True)
            build = self._build(target, out)
            for f in build["files"]:
                if f.endswith(".py"):
                    result = subprocess.run(
                        [sys.executable, "-m", "py_compile", str(out / f)],
                        capture_output=True, text=True,
                    )
                    assert result.returncode == 0, f"{target}/{f} failed to compile: {result.stderr}"

    def test_generated_cli_runs(self, tmp_path):
        self._build("cli", tmp_path)
        result = subprocess.run(
            [sys.executable, str(tmp_path / "main.py"), "--list"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr
        assert "Upload" in result.stdout or "OCR" in result.stdout or "capabilit" in result.stdout.lower()

    def test_generated_mcp_flow(self, tmp_path):
        self._build("mcp", tmp_path)
        test_script = tmp_path / "tests" / "test_mcp.py"
        assert test_script.exists(), "test_mcp.py should be generated"
        result = subprocess.run(
            [sys.executable, str(test_script), str(tmp_path / "server.py")],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr
        assert "OK" in result.stdout

    def test_llm_off_when_use_llm_false(self, tmp_path):
        build = self._build("cli", tmp_path)
        assert build["smoke_ok"] is True
