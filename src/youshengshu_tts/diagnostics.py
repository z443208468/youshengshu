import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import requests

from .config import TtsAppConfig, load_tts_config


@dataclass
class CheckResult:
    name: str
    ok: bool
    severity: str
    message: str
    detail: dict = field(default_factory=dict)


def _ok(name: str, message: str, detail: Optional[dict] = None) -> CheckResult:
    return CheckResult(name=name, ok=True, severity="info", message=message, detail=detail or {})


def _warning(name: str, message: str, detail: Optional[dict] = None) -> CheckResult:
    return CheckResult(name=name, ok=False, severity="warning", message=message, detail=detail or {})


def _error(name: str, message: str, detail: Optional[dict] = None) -> CheckResult:
    return CheckResult(name=name, ok=False, severity="error", message=message, detail=detail or {})


def check_config(config: TtsAppConfig) -> CheckResult:
    try:
        from .config import validate_tts_config

        validate_tts_config(config)
        return _ok("tts_config", "TTS 配置有效")
    except Exception as exc:
        return _error("tts_config", f"TTS 配置无效: {exc}")


def check_source_path(config: TtsAppConfig) -> CheckResult:
    path = Path(config.paths.source_path)
    if config.paths.source_mode == "txt_file":
        if not path.exists() or not path.is_file():
            return _error("source_path", f"TXT 文件不存在: {path}")
        return _ok("source_path", f"TXT 文件存在: {path}")

    if not path.exists() or not path.is_dir():
        return _error("source_path", f"中文章节目录不存在: {path}")
    txt_files = list(path.glob("*.txt"))
    if not txt_files:
        return _warning("source_path", f"中文章节目录没有 txt 文件: {path}")
    return _ok("source_path", f"中文章节目录存在，txt 文件数: {len(txt_files)}")


def check_manifest(config: TtsAppConfig) -> CheckResult:
    from .manifest import load_manifest

    manifest_path = Path(config.paths.manifest_file)
    if not manifest_path.exists():
        return _warning("manifest", f"TTS manifest 尚未创建: {manifest_path}")
    try:
        manifest = load_manifest(manifest_path)
        return _ok(
            "manifest",
            f"TTS manifest 可读，章节数: {len(manifest.chapters)}",
            {"manifest_file": str(manifest_path)},
        )
    except Exception as exc:
        return _error("manifest", f"TTS manifest 读取失败: {exc}")


def check_cosyvoice_service(config: TtsAppConfig) -> CheckResult:
    base_url = config.cosyvoice.base_url.rstrip("/")
    try:
        response = requests.get(f"{base_url}/docs", timeout=5)
        if response.ok:
            return _ok("cosyvoice_http", f"CosyVoice HTTP 可访问: {base_url}")
        return _warning(
            "cosyvoice_http",
            f"CosyVoice HTTP 返回 {response.status_code}: {base_url}",
        )
    except Exception as exc:
        return _warning("cosyvoice_http", f"CosyVoice HTTP 不可访问: {exc}")


def run_diagnostics(config: TtsAppConfig) -> list[CheckResult]:
    return [
        check_config(config),
        check_source_path(config),
        check_manifest(config),
        check_cosyvoice_service(config),
    ]


def doctor_payload(config: TtsAppConfig) -> dict:
    checks = run_diagnostics(config)
    errors = [c for c in checks if c.severity == "error"]
    warnings = [c for c in checks if c.severity == "warning"]
    return {
        "ok": len(errors) == 0,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "checks": [asdict(c) for c in checks],
    }
