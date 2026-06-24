import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from youshengshu_tts.runtime import has_model_files  # noqa: E402


def download_from_huggingface(repo_id: str, target_dir: Path) -> None:
    from huggingface_hub import snapshot_download

    snapshot_download(
        repo_id=repo_id,
        local_dir=str(target_dir),
        local_dir_use_symlinks=False,
    )


def download_from_modelscope(repo_id: str, target_dir: Path) -> None:
    from modelscope import snapshot_download

    snapshot_download(
        repo_id,
        local_dir=str(target_dir),
    )


def prepare_target_dir(target_dir: Path) -> None:
    if has_model_files(target_dir):
        return

    if target_dir.exists():
        shutil.rmtree(target_dir)

    target_dir.mkdir(parents=True, exist_ok=True)


def reset_target_dir(target_dir: Path) -> None:
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-dir", required=True)
    parser.add_argument("--hf-repo", required=True)
    parser.add_argument("--modelscope-repo", required=True)
    args = parser.parse_args()

    target_dir = Path(args.target_dir)
    prepare_target_dir(target_dir)

    errors: list[str] = []

    try:
        download_from_huggingface(args.hf_repo, target_dir)
        if has_model_files(target_dir):
            print(f"[OK] downloaded from HuggingFace: {args.hf_repo}", flush=True)
            return 0
        errors.append("HuggingFace download completed but model files are incomplete")
    except Exception as exc:
        errors.append(f"HuggingFace failed: {exc}")

    reset_target_dir(target_dir)

    try:
        download_from_modelscope(args.modelscope_repo, target_dir)
        if has_model_files(target_dir):
            print(f"[OK] downloaded from ModelScope: {args.modelscope_repo}", flush=True)
            return 0
        errors.append("ModelScope download completed but model files are incomplete")
    except Exception as exc:
        errors.append(f"ModelScope failed: {exc}")

    raise RuntimeError("; ".join(errors))


if __name__ == "__main__":
    raise SystemExit(main())
