import json
import tempfile
from pathlib import Path

import pytest

from youshengshu.config import AppConfig, PathsConfig, ChunkingConfig, TranslationConfig
from youshengshu.progress import (
    TranslationManifest,
    ManifestChapter,
    TRANSLATION_STATUS_PENDING,
    TRANSLATION_STATUS_FAILED,
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

        # Create en_chapters dir with one chapter file
        en_dir = tmpdir / "en_chapters"
        en_dir.mkdir(parents=True, exist_ok=True)
        chapter_file = en_dir / "chapter_001_en.txt"
        chapter_file.write_text("This is a test chapter body.", encoding="utf-8")

        # Create manifest with one pending chapter
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

        # Run pipeline - should catch the failure and save manifest
        results = run_translation_pipeline(config, client, manifest, max_chapters=1)

        # Manifest file should exist
        assert manifest_path.exists(), "Manifest should have been saved"

        # Reload manifest and check status
        loaded = TranslationManifest.load(manifest_path)
        assert len(loaded.chapters) == 1
        ch = loaded.chapters[0]
        assert ch.translation_status == TRANSLATION_STATUS_FAILED, (
            f"Expected failed, got {ch.translation_status}"
        )
        assert ch.error is not None
        assert "fake failure" in ch.error
