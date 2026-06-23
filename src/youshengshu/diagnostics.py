import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional

from .config import load_config
from .exceptions import LMStudioError
from .lmstudio_client import LMStudioClient


@dataclass
class CheckResult:
    name: str
    ok: bool
    severity: str  # "info" | "warning" | "error"
    message: str
    detail: dict = field(default_factory=dict)


def _ok(name: str, message: str, detail: Optional[dict] = None) -> CheckResult:
    return CheckResult(name=name, ok=True, severity="info", message=message, detail=detail or {})


def _warning(name: str, message: str, detail: Optional[dict] = None) -> CheckResult:
    return CheckResult(name=name, ok=False, severity="warning", message=message, detail=detail or {})


def _error(name: str, message: str, detail: Optional[dict] = None) -> CheckResult:
    return CheckResult(name=name, ok=False, severity="error", message=message, detail=detail or {})


def check_python_version() -> CheckResult:
    v = sys.version_info
    if v.major >= 3 and v.minor >= 8:
        return _ok("python_version", f"Python {v.major}.{v.minor}.{v.micro}")
    return _error("python_version", f"Python 版本过低: {v.major}.{v.minor}.{v.micro}，需要 >= 3.8")


def check_config_file(config_path: str) -> CheckResult:
    path = Path(config_path)
    if not path.exists():
        return _error("config_file", f"配置文件不存在: {config_path}")
    try:
        load_config(config_path)
        return _ok("config_file", f"配置文件可读: {config_path}")
    except Exception as e:
        return _error("config_file", f"配置文件格式错误: {e}")


def check_repo_structure() -> CheckResult:
    """Verify that the project structure looks correct relative to CWD."""
    cwd = Path.cwd()
    markers = [
        cwd / "src" / "youshengshu" / "cli.py",
        cwd / "requirements.txt",
    ]
    missing = [str(m) for m in markers if not m.exists()]
    if missing:
        return _error("repo_structure", f"仓库结构不完整，缺失文件: {', '.join(missing)}")
    return _ok("repo_structure", f"仓库结构正确: {cwd}")


def check_input_file(raw_path: str) -> CheckResult:
    path = Path(raw_path)
    if not path.exists():
        return _error("input_file", f"输入文件不存在: {raw_path}")
    return _ok("input_file", f"输入文件存在: {raw_path}")


def check_output_dirs(en_dir: str, cn_dir: str) -> CheckResult:
    """Check that output dirs exist or are creatable."""
    issues = []
    for name, d in [("en_chapters_dir", en_dir), ("cn_chapters_dir", cn_dir)]:
        p = Path(d)
        if p.exists() and not p.is_dir():
            issues.append(f"{name} 存在但不是目录: {d}")
        elif not p.exists():
            try:
                p.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                issues.append(f"{name} 无法创建: {d} ({e})")
    if issues:
        return _warning("output_dirs", "; ".join(issues))
    return _ok("output_dirs", "输出目录可用")


def check_manifest_parent(raw_path: str) -> CheckResult:
    parent = Path(raw_path).parent
    if not parent.exists():
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return _warning("manifest_parent", f"Manifest 目录无法创建: {parent} ({e})")
        return _ok("manifest_parent", f"Manifest 目录已创建: {parent}")
    return _ok("manifest_parent", f"Manifest 目录存在: {parent}")


def check_lmstudio(config_lmstudio) -> CheckResult:
    from .config import LMStudioConfig, _filter_dataclass_kwargs

    if isinstance(config_lmstudio, dict):
        cfg = LMStudioConfig(**_filter_dataclass_kwargs(LMStudioConfig, config_lmstudio))
    else:
        cfg = config_lmstudio

    # Use a short timeout (5s) for the diagnostic check — the config's
    # request_timeout_seconds (default 600s) is meant for actual translation.
    import copy
    check_cfg = copy.copy(cfg)
    check_cfg.request_timeout_seconds = 5

    client = LMStudioClient(check_cfg)
    try:
        model_id = client.resolve_model_id()
        return _ok("lmstudio", f"LM Studio 可连接，当前模型: {model_id}", {"model_id": model_id})
    except LMStudioError as e:
        message = str(e)

        if "无法连接到 LM Studio API" in message:
            return _warning(
                "lmstudio",
                "LM Studio 未启动或不可连接（不影响分章节）",
                {"error": message},
            )

        if "当前没有加载模型" in message:
            return _error(
                "lmstudio",
                "LM Studio 在线但未加载可用模型（翻译不可用）",
                {"error": message},
            )

        return _error(
            "lmstudio",
            "LM Studio 状态异常（翻译不可用）",
            {"error": message},
        )
    except Exception as e:
        return _warning(
            "lmstudio",
            "LM Studio 检查异常（不影响分章节）",
            {"error": str(e)},
        )


def run_diagnostics(config_path: str) -> dict:
    """Run all health checks and return a structured result.

    Severity levels:
      - error (fatal in python_version/repo_structure): app cannot function
      - error (other): blocks specific operations
      - warning: does not block anything, informational
    """
    config = load_config(config_path)

    checks = [
        check_python_version(),
        check_config_file(config_path),
        check_repo_structure(),
        check_input_file(config.paths.input_file),
        check_output_dirs(config.paths.en_chapters_dir, config.paths.cn_chapters_dir),
        check_manifest_parent(config.paths.manifest_file),
        check_lmstudio(config.lmstudio),
    ]

    fatal_names = {"python_version", "repo_structure"}
    fatal = {c.name for c in checks if c.severity == "error" and c.name in fatal_names}
    input_ok = next((c.ok for c in checks if c.name == "input_file"), False)
    lmstudio_check = next((c for c in checks if c.name == "lmstudio"), None)
    lmstudio_translate_ok = (
        lmstudio_check is not None
        and lmstudio_check.ok
        and lmstudio_check.severity != "error"
    ) if lmstudio_check else False

    return {
        "ok": len(fatal) == 0,
        "can_split": len(fatal) == 0 and input_ok,
        "can_translate": len(fatal) == 0 and input_ok and lmstudio_translate_ok,
        "checks": [asdict(c) for c in checks],
    }
