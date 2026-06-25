from pathlib import Path
import importlib.util
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from youshengshu_tts.runtime import check_cosyvoice_runtime, has_model_files, required_python_version

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


def test_resolve_cosyvoice_venv_creator_uses_required_version_and_fallbacks_to_sys_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import subprocess
    import sys

    calls: list[list[str]] = []

    class Result:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_required_python_version(model_profile: str) -> str:
        return "3.10"

    def fake_run(args, **kwargs):
        calls.append(args)

        if args[0] == "py":
            raise FileNotFoundError("py not found")

        if args[0] == sys.executable:
            return Result(0, "3.10\n")

        return Result(1, "", "not compatible")

    monkeypatch.setattr(_bootstrap_mod, "required_python_version", fake_required_python_version)
    monkeypatch.setattr(subprocess, "run", fake_run)

    selected = _bootstrap_mod.resolve_cosyvoice_venv_creator("cosyvoice_300m_sft")

    assert selected == [sys.executable]
    assert any(call[0] == "py" for call in calls)
    assert any(call[0] == sys.executable for call in calls)


def test_required_python_version_can_be_overridden_by_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YSS_COSYVOICE_PYTHON_VERSION", "3.11")

    assert required_python_version("cosyvoice_300m_sft") == "3.11"


def test_python_candidates_do_not_hardcode_local_python_path() -> None:
    candidates = _bootstrap_mod.python_candidates("3.10")
    rendered = [" ".join(candidate) for candidate in candidates]

    assert "C:/Python310/python.exe" not in rendered
    assert "C:/Program Files/Python310/python.exe" not in rendered


def test_build_constraints_file_exists() -> None:
    path = REPO_ROOT / "tools" / "tts" / "cosyvoice_build_constraints.txt"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "setuptools<70" in text
    assert "wheel" in text


def test_pip_install_env_uses_constraints() -> None:
    env = _bootstrap_mod.pip_install_env(REPO_ROOT)
    assert "PIP_CONSTRAINT" in env
    assert env["PIP_CONSTRAINT"].endswith("tools\\tts\\cosyvoice_build_constraints.txt") or env[
        "PIP_CONSTRAINT"
    ].endswith("tools/tts/cosyvoice_build_constraints.txt")
    assert env["PIP_NO_INPUT"] == "1"


def test_install_requirements_orders_build_backend_before_whisper_before_requirements(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[str] = []

    fake_repo = tmp_path
    cosyvoice_dir = fake_repo / "third_party" / "tts" / "CosyVoice"
    cosyvoice_dir.mkdir(parents=True)
    requirements = cosyvoice_dir / "requirements.txt"
    requirements.write_text("openai-whisper==20231117\n", encoding="utf-8")

    venv_python = fake_repo / "third_party" / "tts" / ".cosyvoice_venv" / "Scripts" / "python.exe"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_text("", encoding="utf-8")

    constraints = fake_repo / "tools" / "tts" / "cosyvoice_build_constraints.txt"
    constraints.parent.mkdir(parents=True)
    constraints.write_text("setuptools<70\nwheel\n", encoding="utf-8")

    def fake_runtime_paths(repo_root: Path) -> dict[str, Path]:
        return {
            "cosyvoice_dir": cosyvoice_dir,
            "model_dir": cosyvoice_dir / "pretrained_models" / "CosyVoice-300M-SFT",
        }

    def fake_run_step(args, cwd=None, env=None):
        calls.append(" ".join(str(x) for x in args))

    whisper_checks = 0

    def fake_probe(args, **kwargs):
        class Result:
            returncode = 0
            stdout = "ok"
            stderr = ""

        nonlocal whisper_checks
        code = args[-1] if args else ""
        if isinstance(code, str) and "import whisper" in code:
            whisper_checks += 1
            if whisper_checks == 1:
                return type("R", (), {"returncode": 1, "stdout": "", "stderr": "no whisper"})()
        return Result()

    monkeypatch.setattr(_bootstrap_mod, "runtime_paths", fake_runtime_paths)
    monkeypatch.setattr(_bootstrap_mod, "run_step", fake_run_step)
    monkeypatch.setattr(_bootstrap_mod, "import_probe_ok", lambda python: True)
    monkeypatch.setattr(_bootstrap_mod.subprocess, "run", fake_probe)

    _bootstrap_mod.install_requirements(fake_repo, venv_python)

    joined = "\n".join(calls)
    assert "setuptools<70" in joined
    assert "openai-whisper==20231117" in joined
    assert "-r" in joined
    assert joined.index("setuptools<70") < joined.index("openai-whisper==20231117")
