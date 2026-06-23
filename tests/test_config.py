import json
from pathlib import Path

from youshengshu.config import load_config


def test_load_config_ignores_legacy_lmstudio_max_output_tokens(tmp_path: Path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "paths": {},
                "chapter_split": {},
                "lmstudio": {
                    "base_url": "http://localhost:1234/v1",
                    "max_output_tokens": 2048,
                },
                "chunking": {
                    "context_tokens": 8192,
                    "reserved_output_tokens": 2048,
                    "safety_ratio": 0.65,
                    "allow_word_split": False,
                    "initial_paragraphs_per_batch": 4,
                },
                "translation": {},
            }
        ),
        encoding="utf-8",
    )

    cfg = load_config(str(config_path))
    assert cfg.chunking.initial_paragraphs_per_batch == 4
    assert not hasattr(cfg.chunking, "context_tokens")
    assert not hasattr(cfg.lmstudio, "max_output_tokens")
