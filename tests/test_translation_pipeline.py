import json
import tempfile
from pathlib import Path

import pytest

from youshengshu.config import AppConfig, PathsConfig, ChunkingConfig, TranslationConfig
from youshengshu.exceptions import ContextOverflowError
from youshengshu.progress import (
    TranslationManifest,
    ManifestChapter,
    TRANSLATION_STATUS_PENDING,
    TRANSLATION_STATUS_FAILED,
    TRANSLATION_STATUS_DONE,
)
from youshengshu.translator import run_translation_pipeline


class FailingClient:
    """A mock LMStudioClient that always fails translation."""
    _resolved_model_id = "fake-model"

    def __init__(self, *args, **kwargs):
        pass

    def resolve_model_id(self) -> str:
        return self._resolved_model_id

    def translate(self, messages, temperature=None, top_p=None, max_tokens=None):
        raise RuntimeError("fake failure")


class OverflowThenSuccessClient:
    _resolved_model_id = "fake-model"

    def __init__(self):
        self.calls = []

    def translate(self, messages, temperature=None, top_p=None, max_tokens=None):
        assert max_tokens is None
        user = messages[-1]["content"]
        source = user.split("下面是原文片段：", 1)[-1].strip()
        paragraph_count = len([p for p in source.split("\n\n") if p.strip()])
        self.calls.append(paragraph_count)

        if paragraph_count > 1:
            raise ContextOverflowError("context length exceeded")

        return "译文"


class AlwaysOverflowClient:
    _resolved_model_id = "fake-model"

    def __init__(self):
        self.calls = 0

    def translate(self, messages, temperature=None, top_p=None, max_tokens=None):
        assert max_tokens is None
        self.calls += 1
        raise ContextOverflowError("context length exceeded")


def _make_minimal_config(tmpdir: Path) -> AppConfig:
    """Create a minimal AppConfig pointing to temp directories."""
    return AppConfig(
        paths=PathsConfig(
            input_file=str(tmpdir / "input.txt"),
            en_chapters_dir=str(tmpdir / "en_chapters"),
            cn_chapters_dir=str(tmpdir / "cn_chapters"),
            manifest_file=str(tmpdir / "manifest.json"),
        ),
        chunking=ChunkingConfig(),
        translation=TranslationConfig(),
    )


def test_manifest_saved_when_translation_fails():
    """When translate_chapter fails, the manifest should still be saved with failed status."""
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)

        en_dir = tmpdir / "en_chapters"
        en_dir.mkdir(parents=True, exist_ok=True)
        chapter_file = en_dir / "chapter_001_en.txt"
        chapter_file.write_text("This is a test chapter body.", encoding="utf-8")

        manifest = TranslationManifest(
            source_file=str(tmpdir / "input.txt"),
            chapters=[
                ManifestChapter(
                    index=1,
                    title="Test Chapter",
                    en_path=str(chapter_file),
                    source_sha256="dummy_sha",
                    translation_status=TRANSLATION_STATUS_PENDING,
                ),
            ],
        )

        config = _make_minimal_config(tmpdir)
        client = FailingClient()

        manifest_path = Path(config.paths.manifest_file)

        run_translation_pipeline(config, client, manifest, max_chapters=1)

        assert manifest_path.exists(), "Manifest should have been saved"

        loaded = TranslationManifest.load(manifest_path)
        assert len(loaded.chapters) == 1
        ch = loaded.chapters[0]
        assert ch.translation_status == TRANSLATION_STATUS_FAILED, (
            f"Expected failed, got {ch.translation_status}"
        )
        assert ch.error is not None
        assert "fake failure" in ch.error


def test_paragraph_batch_reduces_on_context_overflow_and_succeeds(tmp_path):
    en_dir = tmp_path / "en_chapters"
    en_dir.mkdir(parents=True)
    chapter_file = en_dir / "chapter_001_en.txt"
    chapter_file.write_text("Para one.\n\nPara two.\n\nPara three.", encoding="utf-8")

    manifest = TranslationManifest(
        source_file=str(tmp_path / "input.txt"),
        chapters=[
            ManifestChapter(
                index=1,
                title="Test Chapter",
                en_path=str(chapter_file),
                source_sha256="dummy_sha",
                translation_status=TRANSLATION_STATUS_PENDING,
            ),
        ],
    )

    config = AppConfig(
        paths=PathsConfig(
            input_file=str(tmp_path / "input.txt"),
            en_chapters_dir=str(en_dir),
            cn_chapters_dir=str(tmp_path / "cn_chapters"),
            manifest_file=str(tmp_path / "manifest.json"),
        ),
        chunking=ChunkingConfig(
            initial_paragraphs_per_batch=2,
            min_paragraphs_per_batch=1,
            overflow_backoff_factor=0.5,
        ),
        translation=TranslationConfig(),
    )

    client = OverflowThenSuccessClient()
    results = run_translation_pipeline(config, client, manifest, max_chapters=1)

    assert len(results) == 1
    assert manifest.chapters[0].translation_status == TRANSLATION_STATUS_DONE
    assert manifest.chapters[0].chunk_count == 3
    assert 2 in client.calls
    assert client.calls.count(1) == 3
    assert Path(manifest.chapters[0].cn_path).exists()


def test_single_paragraph_context_overflow_fails_without_splitting(tmp_path):
    en_dir = tmp_path / "en_chapters"
    en_dir.mkdir(parents=True)
    chapter_file = en_dir / "chapter_001_en.txt"
    chapter_file.write_text("word " * 10000, encoding="utf-8")

    manifest = TranslationManifest(
        source_file=str(tmp_path / "input.txt"),
        chapters=[
            ManifestChapter(
                index=1,
                title="Test Chapter",
                en_path=str(chapter_file),
                source_sha256="dummy_sha",
                translation_status=TRANSLATION_STATUS_PENDING,
            ),
        ],
    )

    config = AppConfig(
        paths=PathsConfig(
            input_file=str(tmp_path / "input.txt"),
            en_chapters_dir=str(en_dir),
            cn_chapters_dir=str(tmp_path / "cn_chapters"),
            manifest_file=str(tmp_path / "manifest.json"),
        ),
        chunking=ChunkingConfig(
            initial_paragraphs_per_batch=1,
            min_paragraphs_per_batch=1,
            overflow_backoff_factor=0.5,
        ),
        translation=TranslationConfig(),
    )

    client = AlwaysOverflowClient()
    results = run_translation_pipeline(config, client, manifest, max_chapters=1)

    assert results == []
    assert client.calls == 1
    assert manifest.chapters[0].translation_status == TRANSLATION_STATUS_FAILED
    assert "单个段落超过 LM Studio 当前上下文能力" in manifest.chapters[0].error
    assert "paragraph_index=0" in manifest.chapters[0].error
    assert not Path(manifest.chapters[0].cn_path).exists()
