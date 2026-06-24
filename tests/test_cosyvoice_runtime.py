from pathlib import Path
import importlib.util
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from youshengshu_tts.runtime import check_cosyvoice_runtime, has_model_files

_bootstrap_spec = importlib.util.spec_from_file_location(
    "bootstrap_cosyvoice_runtime",
    ROOT / "tools" / "tts" / "bootstrap_cosyvoice_runtime.py",
)
_bootstrap_mod = importlib.util.module_from_spec(_bootstrap_spec)
assert _bootstrap_spec.loader is not None
_bootstrap_spec.loader.exec_module(_bootstrap_mod)
quarantine_path = _bootstrap_mod.quarantine_path


def test_check_runtime_missing(tmp_path: Path) -> None:
    status = check_cosyvoice_runtime(tmp_path)
    assert status.ready is False
    assert "cosyvoice_repo" in status.missing
    assert "fastapi_server" in status.missing
    assert "cosyvoice_venv" in status.missing
    assert "cosyvoice_model" in status.missing


def test_check_runtime_ready(tmp_path: Path) -> None:
    cosyvoice = tmp_path / "third_party" / "tts" / "CosyVoice"
    (cosyvoice / ".git").mkdir(parents=True)
    fastapi_dir = cosyvoice / "runtime" / "python" / "fastapi"
    fastapi_dir.mkdir(parents=True)
    (fastapi_dir / "server.py").write_text("# test", encoding="utf-8")

    venv_python = tmp_path / "third_party" / "tts" / ".cosyvoice_venv" / "Scripts" / "python.exe"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_bytes(b"")

    model_dir = cosyvoice / "pretrained_models" / "CosyVoice-300M-SFT"
    model_dir.mkdir(parents=True)
    (model_dir / "cosyvoice.yaml").write_text("dummy", encoding="utf-8")
    (model_dir / "model.pt").write_bytes(b"dummy")

    status = check_cosyvoice_runtime(tmp_path)
    assert status.ready is True
    assert status.missing == []


def test_has_model_files_requires_config_and_weights(tmp_path: Path) -> None:
    assert has_model_files(tmp_path) is False
    (tmp_path / "cosyvoice.yaml").write_text("dummy", encoding="utf-8")
    assert has_model_files(tmp_path) is False
    (tmp_path / "model.pt").write_bytes(b"dummy")
    assert has_model_files(tmp_path) is True


def test_has_model_files_false_when_only_directory_exists(tmp_path: Path) -> None:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    assert has_model_files(model_dir) is False


def test_has_model_files_false_when_only_config_exists(tmp_path: Path) -> None:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "cosyvoice.yaml").write_text("dummy", encoding="utf-8")
    assert has_model_files(model_dir) is False


def test_check_runtime_model_dir_incomplete_is_not_ready(tmp_path: Path) -> None:
    model_dir = (
        tmp_path
        / "third_party"
        / "tts"
        / "CosyVoice"
        / "pretrained_models"
        / "CosyVoice-300M-SFT"
    )
    model_dir.mkdir(parents=True)
    status = check_cosyvoice_runtime(tmp_path)
    assert status.ready is False
    assert "cosyvoice_model" in status.missing


def test_quarantine_path_moves_invalid_dir(tmp_path: Path) -> None:
    invalid = tmp_path / "third_party" / "tts" / "CosyVoice"
    invalid.mkdir(parents=True)
    (invalid / "junk.txt").write_text("junk", encoding="utf-8")

    moved = quarantine_path(invalid, "not_git_repo")

    assert not invalid.exists()
    assert moved.exists()
    assert moved.name.startswith("CosyVoice.invalid.not_git_repo.")
    assert (moved / "junk.txt").exists()
