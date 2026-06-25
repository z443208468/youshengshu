import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from youshengshu_tts.runtime import (  # noqa: E402
    COSYVOICE_REPO_URL,
    DEFAULT_MODEL_PROFILE,
    MODEL_PROFILES,
    check_cosyvoice_runtime,
    has_model_files,
    required_python_version,
    runtime_paths,
)


def emit(event: str, message: str, detail: dict | None = None) -> None:
    payload = {
        "event": event,
        "message": message,
        "detail": detail or {},
    }
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def run_step(
    args: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> None:
    emit("command_start", " ".join(args), {"cwd": str(cwd) if cwd else ""})

    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    try:
        result = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            env=merged_env,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"command executable not found: {args[0]}; "
            f"command={' '.join(args)}; "
            f"cwd={str(cwd) if cwd else ''}"
        ) from exc

    if result.stdout.strip():
        emit("command_stdout", result.stdout.strip())

    if result.stderr.strip():
        emit("command_stderr", result.stderr.strip())

    if result.returncode != 0:
        raise RuntimeError(
            f"command failed: {' '.join(args)} code={result.returncode}\n"
            f"stdout={result.stdout[-4000:]}\n"
            f"stderr={result.stderr[-4000:]}"
        )

    emit("command_done", " ".join(args))


def quarantine_path(path: Path, reason: str) -> Path:
    if not path.exists():
        return path

    parent = path.parent
    safe_reason = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in reason)
    index = 1

    while True:
        candidate = parent / f"{path.name}.invalid.{safe_reason}.{index}"
        if not candidate.exists():
            path.rename(candidate)
            emit(
                "quarantine",
                "Moved invalid CosyVoice directory aside",
                {"from": str(path), "to": str(candidate), "reason": reason},
            )
            return candidate
        index += 1


def ensure_repo(repo_root: Path) -> None:
    paths = runtime_paths(repo_root)
    cosyvoice_dir = paths["cosyvoice_dir"]

    if cosyvoice_dir.exists() and not (cosyvoice_dir / ".git").exists():
        quarantine_path(cosyvoice_dir, "not_git_repo")

    if (cosyvoice_dir / ".git").exists():
        emit("repo_exists", "CosyVoice repo already exists", {"path": str(cosyvoice_dir)})
        run_step(["git", "submodule", "update", "--init", "--recursive"], cwd=cosyvoice_dir)
        return

    cosyvoice_dir.parent.mkdir(parents=True, exist_ok=True)

    run_step(
        [
            "git",
            "clone",
            "--recursive",
            COSYVOICE_REPO_URL,
            str(cosyvoice_dir),
        ]
    )
    run_step(["git", "submodule", "update", "--init", "--recursive"], cwd=cosyvoice_dir)


def ensure_fastapi_server(repo_root: Path) -> None:
    paths = runtime_paths(repo_root)
    cosyvoice_dir = paths["cosyvoice_dir"]
    server_py = paths["fastapi_server_path"]

    if server_py.exists():
        emit("fastapi_ok", "CosyVoice FastAPI server.py exists", {"path": str(server_py)})
        return

    if cosyvoice_dir.exists():
        quarantine_path(cosyvoice_dir, "missing_fastapi_server")

    ensure_repo(repo_root)

    paths = runtime_paths(repo_root)
    server_py = paths["fastapi_server_path"]

    if not server_py.exists():
        raise RuntimeError(f"CosyVoice FastAPI server.py missing after repair clone: {server_py}")

    emit("fastapi_ok", "CosyVoice FastAPI server.py exists after repair", {"path": str(server_py)})


def python_candidates(required_version: str) -> list[list[str]]:
    candidates: list[list[str]] = []

    env_python = os.environ.get("YSS_COSYVOICE_PYTHON", "").strip()
    if env_python:
        candidates.append([env_python])

    if os.name == "nt":
        candidates.append(["py", f"-{required_version}"])

    candidates.append([sys.executable])

    if os.name == "nt":
        candidates.append(["python"])
        candidates.append(["python3"])
    else:
        candidates.append(["python3"])
        candidates.append(["python"])

    deduped: list[list[str]] = []
    seen: set[str] = set()

    for candidate in candidates:
        key = "\0".join(candidate)
        if key not in seen:
            seen.add(key)
            deduped.append(candidate)

    return deduped


def read_python_version_from_command(command: list[str]) -> str | None:
    code = "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"

    try:
        result = subprocess.run(
            [*command, "-c", code],
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError:
        return None

    if result.returncode != 0:
        return None

    version = result.stdout.strip()
    return version or None


def resolve_cosyvoice_venv_creator(model_profile: str) -> list[str]:
    required_version = required_python_version(model_profile)
    checked: list[dict[str, str]] = []

    for candidate in python_candidates(required_version):
        version = read_python_version_from_command(candidate)
        checked.append({
            "command": " ".join(candidate),
            "version": version or "unavailable",
        })

        if version == required_version:
            emit(
                "python_runtime_selected",
                "Selected Python runtime for CosyVoice venv creation",
                {
                    "required_version": required_version,
                    "command": " ".join(candidate),
                    "checked": checked,
                },
            )
            return candidate

    raise RuntimeError(
        "No compatible Python runtime found for CosyVoice; "
        f"required_version={required_version}; "
        f"checked={checked}. "
        "Set YSS_COSYVOICE_PYTHON to a compatible Python executable, "
        "or set YSS_COSYVOICE_PYTHON_VERSION only if CosyVoice requirements were verified for that version."
    )


def read_python_version(python_path: Path) -> str:
    code = "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    return subprocess.check_output(
        [str(python_path), "-c", code],
        text=True,
        encoding="utf-8",
        errors="replace",
    ).strip()


def ensure_venv(repo_root: Path, venv_creator: list[str], model_profile: str) -> Path:
    paths = runtime_paths(repo_root)
    venv_python = paths["venv_python"]
    venv_dir = paths["venv_dir"]
    required_version = required_python_version(model_profile)

    if venv_python.exists():
        version = read_python_version(venv_python)
        if version == required_version:
            emit(
                "venv_exists",
                "CosyVoice venv already exists",
                {
                    "python": str(venv_python),
                    "version": version,
                    "required_version": required_version,
                },
            )
            return venv_python

        emit(
            "venv_recreate",
            "Existing CosyVoice venv has incompatible Python version; recreating",
            {
                "python": str(venv_python),
                "version": version,
                "required_version": required_version,
            },
        )
        shutil.rmtree(venv_dir)

    emit(
        "venv_create",
        "Creating CosyVoice isolated venv",
        {
            "venv": str(venv_dir),
            "creator": " ".join(venv_creator),
            "required_version": required_version,
        },
    )
    run_step([*venv_creator, "-m", "venv", str(venv_dir)])

    if not venv_python.exists():
        raise RuntimeError(f"CosyVoice venv python missing after create: {venv_python}")

    version = read_python_version(venv_python)
    if version != required_version:
        raise RuntimeError(
            f"CosyVoice venv Python version mismatch; "
            f"required={required_version}; got={version}; python={venv_python}"
        )

    return venv_python


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def requirements_marker_path(venv_python: Path) -> Path:
    return venv_python.parent.parent / ".yss_requirements_sha256"


def build_constraints_path(repo_root: Path) -> Path:
    return repo_root / "tools" / "tts" / "cosyvoice_build_constraints.txt"


def pip_install_env(repo_root: Path) -> dict[str, str]:
    constraints = build_constraints_path(repo_root)

    if not constraints.exists():
        raise RuntimeError(f"CosyVoice build constraints file missing: {constraints}")

    return {
        "PIP_CONSTRAINT": str(constraints),
        "PIP_NO_INPUT": "1",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
    }


def ensure_build_backend(repo_root: Path, venv_python: Path) -> None:
    env = pip_install_env(repo_root)

    run_step(
        [
            str(venv_python),
            "-m",
            "pip",
            "install",
            "--upgrade",
            "pip",
        ],
        env=env,
    )

    run_step(
        [
            str(venv_python),
            "-m",
            "pip",
            "install",
            "--upgrade",
            "setuptools<70",
            "wheel",
        ],
        env=env,
    )

    result = subprocess.run(
        [
            str(venv_python),
            "-c",
            "import pkg_resources, setuptools, wheel; print('build-backend-ok')",
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "CosyVoice build backend probe failed; "
            f"stdout={result.stdout}; stderr={result.stderr}"
        )

    emit("build_backend_ok", "CosyVoice build backend is ready")


def ensure_openai_whisper(repo_root: Path, venv_python: Path) -> None:
    env = pip_install_env(repo_root)

    result = subprocess.run(
        [
            str(venv_python),
            "-c",
            "import whisper; print('openai-whisper-ok')",
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if result.returncode == 0:
        emit("openai_whisper_exists", "openai-whisper already importable")
        return

    run_step(
        [
            str(venv_python),
            "-m",
            "pip",
            "install",
            "--no-build-isolation",
            "openai-whisper==20231117",
        ],
        env=env,
    )

    result = subprocess.run(
        [
            str(venv_python),
            "-c",
            "import whisper; print('openai-whisper-ok')",
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "openai-whisper import probe failed after install; "
            f"stdout={result.stdout}; stderr={result.stderr}"
        )

    emit("openai_whisper_ok", "openai-whisper installed and importable")


def import_probe_ok(venv_python: Path) -> bool:
    code = (
        "import fastapi, uvicorn, requests, numpy, torch, torchaudio, "
        "huggingface_hub, modelscope, whisper; "
        "print('ok')"
    )
    result = subprocess.run(
        [str(venv_python), "-c", code],
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.returncode == 0


def install_requirements(repo_root: Path, venv_python: Path) -> None:
    paths = runtime_paths(repo_root)
    cosyvoice_dir = paths["cosyvoice_dir"]
    requirements = cosyvoice_dir / "requirements.txt"

    if not requirements.exists():
        raise RuntimeError(f"CosyVoice requirements.txt missing: {requirements}")

    marker = requirements_marker_path(venv_python)
    current_hash = file_sha256(requirements)
    env = pip_install_env(repo_root)

    if (
        marker.exists()
        and marker.read_text(encoding="utf-8").strip() == current_hash
        and import_probe_ok(venv_python)
    ):
        emit("requirements_exists", "CosyVoice requirements already installed", {"marker": str(marker)})
        return

    ensure_build_backend(repo_root, venv_python)
    ensure_openai_whisper(repo_root, venv_python)

    run_step(
        [
            str(venv_python),
            "-m",
            "pip",
            "install",
            "-r",
            str(requirements),
        ],
        cwd=cosyvoice_dir,
        env=env,
    )

    run_step(
        [
            str(venv_python),
            "-m",
            "pip",
            "install",
            "huggingface_hub",
            "modelscope",
        ],
        env=env,
    )

    if not import_probe_ok(venv_python):
        raise RuntimeError("CosyVoice dependency import probe failed after pip install")

    marker.write_text(current_hash, encoding="utf-8")


def gpu_runtime_manifest_path(repo_root: Path) -> Path:
    return repo_root / "tools" / "tts" / "cosyvoice_gpu_runtime.json"


def load_gpu_runtime_manifest(repo_root: Path) -> dict:
    path = gpu_runtime_manifest_path(repo_root)
    if not path.exists():
        raise RuntimeError(f"CosyVoice GPU runtime manifest missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def gpu_runtime_marker_path(venv_python: Path) -> Path:
    return venv_python.parent.parent / ".yss_gpu_runtime_sha256"


def gpu_runtime_fingerprint(repo_root: Path) -> str:
    manifest_path = gpu_runtime_manifest_path(repo_root)
    constraints_path = repo_root / "tools" / "tts" / "cosyvoice_gpu_constraints.txt"

    digest = hashlib.sha256()
    digest.update(manifest_path.read_bytes())
    digest.update(b"\n---constraints---\n")
    digest.update(constraints_path.read_bytes())
    return digest.hexdigest()


def gpu_pip_install_env() -> dict[str, str]:
    """GPU torch reinstall must not inherit setuptools<70 from cosyvoice_build_constraints."""
    return {
        "PIP_NO_INPUT": "1",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
    }


def install_gpu_torch_runtime(repo_root: Path, venv_python: Path) -> None:
    manifest = load_gpu_runtime_manifest(repo_root)
    index_url = manifest["cuda_index_url"]
    torch_version = manifest["torch"]
    torchaudio_version = manifest["torchaudio"]

    run_step(
        [
            str(venv_python),
            "-m",
            "pip",
            "install",
            "--upgrade",
            "--force-reinstall",
            f"torch=={torch_version}",
            f"torchaudio=={torchaudio_version}",
            "--index-url",
            index_url,
        ],
        env=gpu_pip_install_env(),
    )

    emit(
        "gpu_torch_runtime_installed",
        "Installed GPU PyTorch runtime",
        {
            "torch": torch_version,
            "torchaudio": torchaudio_version,
            "index_url": index_url,
        },
    )


def verify_gpu_torch_runtime(repo_root: Path, venv_python: Path) -> None:
    code = r'''
import json
import torch

payload = {
    "torch_version": torch.__version__,
    "torch_cuda": torch.version.cuda,
    "cuda_available": torch.cuda.is_available(),
    "device_name": None,
    "device_capability": None,
    "arch_list": [],
    "sm_supported_by_arch_list": False,
    "cuda_kernel_ok": False,
}

payload["arch_list"] = list(torch.cuda.get_arch_list())

if not torch.cuda.is_available():
    print(json.dumps(payload, ensure_ascii=False))
    raise SystemExit(10)

device_name = torch.cuda.get_device_name(0)
major, minor = torch.cuda.get_device_capability(0)
sm = f"sm_{major}{minor}"

payload["device_name"] = device_name
payload["device_capability"] = sm
payload["sm_supported_by_arch_list"] = sm in set(payload["arch_list"])

x = torch.randn((256, 256), device="cuda", dtype=torch.float32)
y = torch.randn((256, 256), device="cuda", dtype=torch.float32)
z = x @ y
torch.cuda.synchronize()
payload["cuda_kernel_ok"] = bool(z.is_cuda and z.numel() == 256 * 256)

print(json.dumps(payload, ensure_ascii=False))

if not payload["cuda_kernel_ok"]:
    raise SystemExit(11)
'''

    result = subprocess.run(
        [str(venv_python), "-c", code],
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()

    if result.returncode != 0:
        raise RuntimeError(
            "CosyVoice GPU torch runtime verification failed; "
            f"returncode={result.returncode}; stdout={stdout}; stderr={stderr}"
        )

    payload = json.loads(stdout.splitlines()[-1])

    if not payload["cuda_available"]:
        raise RuntimeError(f"CUDA unavailable after GPU torch install: {payload}")

    if not payload["cuda_kernel_ok"]:
        raise RuntimeError(f"CUDA kernel smoke failed after GPU torch install: {payload}")

    manifest = load_gpu_runtime_manifest(repo_root)
    expected_cuda = manifest.get("expected_cuda")
    expected_device_contains = manifest.get("expected_device_contains")
    expected_device_capability = manifest.get("expected_device_capability")

    if expected_cuda and payload["torch_cuda"] != expected_cuda:
        raise RuntimeError(
            f"GPU torch CUDA version mismatch; expected={expected_cuda}; payload={payload}"
        )

    if expected_device_contains and expected_device_contains.lower() not in (
        payload["device_name"] or ""
    ).lower():
        raise RuntimeError(
            "GPU device mismatch; "
            f"expected contains={expected_device_contains}; payload={payload}"
        )

    if expected_device_capability and payload["device_capability"] != expected_device_capability:
        raise RuntimeError(
            "GPU capability mismatch; "
            f"expected={expected_device_capability}; payload={payload}"
        )

    emit("gpu_torch_runtime_ok", "GPU PyTorch runtime verified", payload)


def ensure_gpu_torch_runtime(repo_root: Path, venv_python: Path) -> None:
    marker = gpu_runtime_marker_path(venv_python)
    fingerprint = gpu_runtime_fingerprint(repo_root)

    if marker.exists() and marker.read_text(encoding="utf-8").strip() == fingerprint:
        try:
            verify_gpu_torch_runtime(repo_root, venv_python)
            emit(
                "gpu_runtime_exists",
                "GPU torch runtime already verified",
                {"marker": str(marker)},
            )
            return
        except Exception as exc:
            emit(
                "gpu_runtime_repair",
                "GPU marker exists but probe failed; reinstalling GPU torch runtime",
                {"error": str(exc)},
            )

    install_gpu_torch_runtime(repo_root, venv_python)
    verify_gpu_torch_runtime(repo_root, venv_python)
    marker.write_text(fingerprint, encoding="utf-8")


def download_model(repo_root: Path, venv_python: Path, model_profile: str) -> None:
    profile = MODEL_PROFILES[model_profile]
    paths = runtime_paths(repo_root)
    model_dir = paths["model_dir"]

    if has_model_files(model_dir):
        emit(
            "model_exists",
            "CosyVoice model already exists and is complete",
            {"model_dir": str(model_dir)},
        )
        return

    script = Path(__file__).with_name("download_cosyvoice_model.py")
    run_step(
        [
            str(venv_python),
            str(script),
            "--target-dir",
            str(model_dir),
            "--hf-repo",
            profile["hf_repo"],
            "--modelscope-repo",
            profile["modelscope_repo"],
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--model-profile", default=DEFAULT_MODEL_PROFILE)
    parser.add_argument("--json-lines", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root)
    venv_creator = resolve_cosyvoice_venv_creator(args.model_profile)

    emit("bootstrap_start", "CosyVoice bootstrap started", {"repo_root": str(repo_root)})

    ensure_repo(repo_root)
    ensure_fastapi_server(repo_root)
    venv_python = ensure_venv(repo_root, venv_creator, args.model_profile)
    install_requirements(repo_root, venv_python)
    ensure_gpu_torch_runtime(repo_root, venv_python)
    download_model(repo_root, venv_python, args.model_profile)

    status = check_cosyvoice_runtime(repo_root)
    if not status.ready:
        raise RuntimeError(f"CosyVoice runtime not ready after bootstrap: {status.missing}")

    emit("bootstrap_done", "CosyVoice runtime ready", status.__dict__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
