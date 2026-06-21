import json
from pathlib import Path


def write_config_json(config_path: str | Path, payload: dict) -> None:
    """Write a configuration dictionary to a JSON config file.

    This is a utility used by tests and as a reference for the Tauri
    Rust backend (which writes the JSON directly).  Kept intentionally
    simple — no schema validation, no default merging.
    """
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
