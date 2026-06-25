from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

COSYVOICE_REPO_URL = "https://github.com/FunAudioLLM/CosyVoice.git"

COSYVOICE_RELATIVE_DIR = Path("third_party/tts/CosyVoice")
COSYVOICE_VENV_RELATIVE_DIR = Path("third_party/tts/.cosyvoice_venv")

FASTAPI_RELATIVE_PATH = Path("runtime/python/fastapi/server.py")
FASTAPI_WORKDIR_RELATIVE_PATH = Path("runtime/python/fastapi")

DEFAULT_MODEL_PROFILE = "cosyvoice_300m_sft"

MODEL_PROFILES = {
    "cosyvoice_300m_sft": {
        "local_dir": "pretrained_models/CosyVoice-300M-SFT",
        "hf_repo": "FunAudioLLM/CosyVoice-300M-SFT",
        "modelscope_repo": "iic/CosyVoice-300M-SFT",
        "supported_modes": ["sft"],
        "default_mode": "sft",
        "default_spk_id": "中文女",
        "python_version": "3.10",
    }
}


def required_python_version(model_profile: str = DEFAULT_MODEL_PROFILE) -> str:
    env_version = os.environ.get("YSS_COSYVOICE_PYTHON_VERSION", "").strip()
    if env_version:
        return env_version

    profile = MODEL_PROFILES[model_profile]
    return profile["python_version"]

BOOTSTRAP_POLL_INTERVAL_MS = 1000
SERVICE_READY_TIMEOUT_SECONDS = 180
SERVICE_READY_MAX_ATTEMPTS = SERVICE_READY_TIMEOUT_SECONDS


@dataclass
class CosyVoiceRuntimeStatus:
    repo_root: str
    cosyvoice_dir: str
    cosyvoice_git_dir: str
    fastapi_server_path: str
    fastapi_workdir: str
    venv_python: str
    model_dir: str
    repo_exists: bool
    git_exists: bool
    fastapi_server_exists: bool
    venv_python_exists: bool
    model_dir_exists: bool
    model_files_exist: bool
    ready: bool
    missing: list[str]


def has_model_files(target_dir: Path) -> bool:
    if not target_dir.exists():
        return False

    has_config = any(
        (target_dir / name).exists()
        for name in ["cosyvoice.yaml", "config.yaml"]
    )

    has_model_weight = any(
        path.suffix.lower() in {".pt", ".pth", ".bin", ".safetensors"}
        for path in target_dir.rglob("*")
        if path.is_file()
    )

    return has_config and has_model_weight


def runtime_paths(repo_root: str | Path) -> dict[str, Path]:
    root = Path(repo_root)
    cosyvoice_dir = root / COSYVOICE_RELATIVE_DIR
    venv_dir = root / COSYVOICE_VENV_RELATIVE_DIR
    if os.name == "nt":
        venv_python = venv_dir / "Scripts" / "python.exe"
    else:
        venv_python = venv_dir / "bin" / "python"

    model_dir = cosyvoice_dir / MODEL_PROFILES[DEFAULT_MODEL_PROFILE]["local_dir"]

    return {
        "cosyvoice_dir": cosyvoice_dir,
        "cosyvoice_git_dir": cosyvoice_dir / ".git",
        "fastapi_server_path": cosyvoice_dir / FASTAPI_RELATIVE_PATH,
        "fastapi_workdir": cosyvoice_dir / FASTAPI_WORKDIR_RELATIVE_PATH,
        "venv_dir": venv_dir,
        "venv_python": venv_python,
        "model_dir": model_dir,
    }


def check_cosyvoice_runtime(repo_root: str | Path) -> CosyVoiceRuntimeStatus:
    paths = runtime_paths(repo_root)

    missing: list[str] = []

    repo_exists = paths["cosyvoice_dir"].exists()
    git_exists = paths["cosyvoice_git_dir"].exists()
    fastapi_server_exists = paths["fastapi_server_path"].exists()
    venv_python_exists = paths["venv_python"].exists()
    model_dir_exists = paths["model_dir"].exists()
    model_files_exist = has_model_files(paths["model_dir"])

    if not repo_exists:
        missing.append("cosyvoice_repo")
    if not git_exists:
        missing.append("cosyvoice_git")
    if not fastapi_server_exists:
        missing.append("fastapi_server")
    if not venv_python_exists:
        missing.append("cosyvoice_venv")
    if not model_files_exist:
        missing.append("cosyvoice_model")

    ready = len(missing) == 0

    return CosyVoiceRuntimeStatus(
        repo_root=str(Path(repo_root)),
        cosyvoice_dir=str(paths["cosyvoice_dir"]),
        cosyvoice_git_dir=str(paths["cosyvoice_git_dir"]),
        fastapi_server_path=str(paths["fastapi_server_path"]),
        fastapi_workdir=str(paths["fastapi_workdir"]),
        venv_python=str(paths["venv_python"]),
        model_dir=str(paths["model_dir"]),
        repo_exists=repo_exists,
        git_exists=git_exists,
        fastapi_server_exists=fastapi_server_exists,
        venv_python_exists=venv_python_exists,
        model_dir_exists=model_dir_exists,
        model_files_exist=model_files_exist,
        ready=ready,
        missing=missing,
    )
