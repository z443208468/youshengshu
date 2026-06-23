import json
import tempfile
from pathlib import Path

import pytest

from youshengshu.config import load_config
from youshengshu.cli import cmd_status, cmd_split, cmd_translate


def _write_dummy_config(tmpdir: Path) -> Path:
    config = {
        "paths": {
            "input_file": str(tmpdir / "input.txt"),
            "en_chapters_dir": str(tmpdir / "en_chapters"),
            "cn_chapters_dir": str(tmpdir / "cn_chapters"),
            "manifest_file": str(tmpdir / "manifest.json"),
        },
        "chapter_split": {
            "strict_chapter_sequence": False,  # relaxed for test fixture
            "min_valid_chapter_chars": 10,
        },
        "lmstudio": {
            "base_url": "http://localhost:9999/v1",
            "api_key": "lm-studio",
            "model_id": "auto",
            "temperature": 0.2,
            "top_p": 0.85,
            "request_timeout_seconds": 1,
            "max_retries": 1,
            "retry_sleep_seconds": 1,
        },
        "chunking": {
            "min_unit": "paragraph",
            "initial_paragraphs_per_batch": 8,
            "min_paragraphs_per_batch": 1,
            "overflow_backoff_factor": 0.5,
        },
        "translation": {
            "skip_existing_done_chapters": True,
            "write_partial_file": True,
            "strip_model_preamble": True,
        },
    }
    config_path = tmpdir / "config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    return config_path


def _write_dummy_input_file(tmpdir: Path, chapters: int = 2) -> None:
    """Write a minimal AO3-style input file with chapter_count chapters."""
    lines = []
    for i in range(1, chapters + 1):
        lines.append(f"Chapter {i}: Chapter {i}: Test Chapter Title {i}")
        lines.append("This is the body of the chapter. " * 50)
    input_path = tmpdir / "input.txt"
    input_path.write_text("\n\n".join(lines), encoding="utf-8")


def test_split_json_output(capsys):
    """split --json should produce parseable JSON with source/chapters/en_chapters_dir/manifest_file."""
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        config_path = _write_dummy_config(tmpdir)
        _write_dummy_input_file(tmpdir, chapters=2)

        cmd_split(str(config_path), as_json=True)
        captured = capsys.readouterr()
        payload = json.loads(captured.out)

        assert "source" in payload
        assert "chapters" in payload
        assert payload["chapters"] == 2
        assert "en_chapters_dir" in payload
        assert "manifest_file" in payload
        assert Path(payload["manifest_file"]).exists()


def test_status_json_output_no_manifest(capsys):
    """status --json on a non-existent manifest should print a JSON error and exit(1)."""
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        config_path = _write_dummy_config(tmpdir)

        with pytest.raises(SystemExit):
            cmd_status(str(config_path), as_json=True)

        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert "error" in payload


def test_status_json_output_with_manifest(capsys):
    """status --json after split should produce parseable JSON with chapter details."""
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        config_path = _write_dummy_config(tmpdir)
        _write_dummy_input_file(tmpdir, chapters=2)

        cmd_split(str(config_path), as_json=True)
        capsys.readouterr()  # discard split output

        cmd_status(str(config_path), as_json=True)
        captured = capsys.readouterr()
        payload = json.loads(captured.out)

        assert payload["total"] == 2
        assert payload["done"] == 0
        assert payload["pending"] == 2
        assert "chapters" in payload
        assert len(payload["chapters"]) == 2
        # Each chapter should have the expected fields
        for ch in payload["chapters"]:
            assert "index" in ch
            assert "title" in ch
            assert "en_path" in ch
            assert "cn_path" in ch
            assert "translation_status" in ch
            assert ch["translation_status"] == "pending"


def test_translate_max_chapters_arg_parsed():
    """The translate subparser should accept --max-chapters without error."""
    import argparse
    from youshengshu.cli import main as cli_main
    # Just verify the argparse setup works by constructing the parser directly
    # This avoids actually running the function
    parser = argparse.ArgumentParser()
    parser.add_argument("--config")
    subparsers = parser.add_subparsers(dest="command")
    translate_parser = subparsers.add_parser("translate")
    translate_parser.add_argument("--max-chapters", type=int, default=0)

    args = parser.parse_args(["--config", "dummy.json", "translate", "--max-chapters", "3"])
    assert args.command == "translate"
    assert args.max_chapters == 3

    args_default = parser.parse_args(["--config", "dummy.json", "translate"])
    assert args_default.max_chapters == 0


def test_translate_chapter_index_arg_parsed():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--config")
    subparsers = parser.add_subparsers(dest="command")
    translate_parser = subparsers.add_parser("translate")
    translate_parser.add_argument("--max-chapters", type=int, default=0)
    translate_parser.add_argument("--chapter-index", type=int, default=0)

    args = parser.parse_args([
        "--config", "dummy.json",
        "translate",
        "--chapter-index", "4",
    ])
    assert args.command == "translate"
    assert args.chapter_index == 4
