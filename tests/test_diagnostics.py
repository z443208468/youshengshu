import json
import tempfile
from pathlib import Path

import pytest

from youshengshu.diagnostics import (
    run_diagnostics,
    check_python_version,
    check_input_file,
    check_lmstudio,
)
from youshengshu.exceptions import LMStudioError


def _make_config(tmpdir: Path, input_file: str = "") -> Path:
    config = {
        "paths": {
            "input_file": input_file or str(tmpdir / "input.txt"),
            "en_chapters_dir": str(tmpdir / "en_chapters"),
            "cn_chapters_dir": str(tmpdir / "cn_chapters"),
            "manifest_file": str(tmpdir / "manifest.json"),
        },
        "chapter_split": {"strict_chapter_sequence": False, "min_valid_chapter_chars": 10},
        "lmstudio": {
            "base_url": "http://localhost:9999/v1",
            "api_key": "lm-studio",
            "model_id": "auto",
            "temperature": 0.2,
            "top_p": 0.85,
            "max_output_tokens": 4096,
            "request_timeout_seconds": 1,
            "max_retries": 1,
            "retry_sleep_seconds": 1,
        },
        "chunking": {},
        "translation": {},
    }
    config_path = tmpdir / "config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    return config_path


def _has_check(result: dict, name: str) -> bool:
    return any(c["name"] == name for c in result["checks"])


def _get_check(result: dict, name: str) -> dict:
    for c in result["checks"]:
        if c["name"] == name:
            return c
    raise AssertionError(f"Check '{name}' not found")


def test_doctor_reports_missing_input_file(monkeypatch):
    """Missing input file should set can_split=False but ok=True (no fatal)."""
    # Prevent actual LM Studio connection attempt
    monkeypatch.setattr(
        "youshengshu.lmstudio_client.LMStudioClient.resolve_model_id",
        lambda self: "fake-model",
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        config_path = _make_config(tmpdir, input_file=str(tmpdir / "missing.txt"))
        result = run_diagnostics(str(config_path))

        assert result["ok"] is True, "missing input is not fatal"
        assert result["can_split"] is False
        assert _has_check(result, "input_file")
        assert _get_check(result, "input_file")["ok"] is False
        assert _get_check(result, "input_file")["severity"] == "error"


def test_doctor_lmstudio_offline_is_warning_not_fatal(monkeypatch):
    """LM Studio connection failure should be warning, not fatal."""
    def mock_resolve(self):
        raise LMStudioError("无法连接到 LM Studio API (http://localhost:9999/v1)。")

    monkeypatch.setattr(
        "youshengshu.lmstudio_client.LMStudioClient.resolve_model_id",
        mock_resolve,
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        config_path = _make_config(tmpdir, input_file=str(tmpdir / "input.txt"))
        Path(tmpdir / "input.txt").write_text("test", encoding="utf-8")

        result = run_diagnostics(str(config_path))

        assert result["ok"] is True, "LM Studio offline should not be fatal"
        assert result["can_translate"] is False
        assert _has_check(result, "lmstudio")
        assert _get_check(result, "lmstudio")["ok"] is False
        assert _get_check(result, "lmstudio")["severity"] == "warning"


def test_doctor_lmstudio_no_model_blocks_translate_only(monkeypatch):
    """LM Studio online but no model loaded should be error that only blocks translate."""
    def mock_resolve(self):
        raise LMStudioError("LM Studio 当前没有加载模型。")

    monkeypatch.setattr(
        "youshengshu.lmstudio_client.LMStudioClient.resolve_model_id",
        mock_resolve,
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        config_path = _make_config(tmpdir, input_file=str(tmpdir / "input.txt"))
        Path(tmpdir / "input.txt").write_text("test", encoding="utf-8")

        result = run_diagnostics(str(config_path))

        assert result["ok"] is True, "no model is not fatal for app"
        assert result["can_translate"] is False
        assert result["can_split"] is True
        assert _has_check(result, "lmstudio")
        assert _get_check(result, "lmstudio")["severity"] == "error"


def test_check_python_version():
    """Python version check should pass on any reasonable Python 3."""
    result = check_python_version()
    assert result.ok is True
    assert result.severity == "info"


def test_check_input_file():
    """check_input_file should return error for non-existent file."""
    result = check_input_file("/nonexistent/path.txt")
    assert result.ok is False
    assert result.severity == "error"

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "exists.txt"
        p.write_text("test", encoding="utf-8")
        result = check_input_file(str(p))
        assert result.ok is True
