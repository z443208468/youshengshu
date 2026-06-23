import json
import tempfile
from pathlib import Path

import pytest

from youshengshu.config import AppConfig, PathsConfig, ChunkingConfig, TranslationConfig
from youshengshu.exceptions import ContextOverflowError, TranslationPipelineStoppedError
from youshengshu.progress import (
    TranslationManifest,
    ManifestChapter,
    TRANSLATION_STATUS_PENDING,
    TRANSLATION_STATUS_FAILED,
    TRANSLATION_STATUS_DONE,
    expected_cn_path_for_en_path,
    expected_resume_state_path_for_cn_path,
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


class FailFirstClient:
    _resolved_model_id = "fake-model"

    def __init__(self):
        self.calls = 0

    def translate(self, messages, temperature=None, top_p=None, max_tokens=None):
        self.calls += 1
        raise RuntimeError("fake failure")


class FailOnSecondBatchClient:
    _resolved_model_id = "fake-model"

    def __init__(self):
        self.calls = 0

    def translate(self, messages, temperature=None, top_p=None, max_tokens=None):
        self.calls += 1
        if self.calls == 2:
            raise RuntimeError("fail second batch")
        return f"译文{self.calls}"


class SuccessClient:
    _resolved_model_id = "fake-model"

    def __init__(self):
        self.translated_chapters = []

    def translate(self, messages, temperature=None, top_p=None, max_tokens=None):
        user = messages[-1]["content"]
        source = user.split("下面是原文片段：", 1)[-1].strip()
        return f"译文:{source[:20]}"


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


def _make_chapter_manifest(tmp_path, chapter_count=1, cn_dir_name="cn_chapters"):
    en_dir = tmp_path / "en_chapters"
    cn_dir = tmp_path / cn_dir_name
    en_dir.mkdir(parents=True, exist_ok=True)
    cn_dir.mkdir(parents=True, exist_ok=True)

    chapters = []
    for i in range(1, chapter_count + 1):
        en_file = en_dir / f"chapter_{i:03d}_en.txt"
        en_file.write_text(f"This is chapter {i} body.", encoding="utf-8")
        chapters.append(
            ManifestChapter(
                index=i,
                title=f"Chapter {i}",
                en_path=str(en_file),
                cn_path=expected_cn_path_for_en_path(str(en_file), str(cn_dir)),
                source_sha256="dummy_sha",
                translation_status=TRANSLATION_STATUS_PENDING,
            )
        )

    return TranslationManifest(
        source_file=str(tmp_path / "input.txt"),
        chapters=chapters,
    )


def test_manifest_saved_when_translation_fails():
    """When translate_chapter fails, the manifest should still be saved with failed status."""
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        manifest = _make_chapter_manifest(tmpdir)
        config = _make_minimal_config(tmpdir)
        client = FailingClient()
        manifest_path = Path(config.paths.manifest_file)

        with pytest.raises(TranslationPipelineStoppedError):
            run_translation_pipeline(config, client, manifest, max_chapters=1)

        assert manifest_path.exists(), "Manifest should have been saved"

        loaded = TranslationManifest.load(manifest_path)
        assert len(loaded.chapters) == 1
        ch = loaded.chapters[0]
        assert ch.translation_status == TRANSLATION_STATUS_FAILED
        assert ch.error is not None
        assert "fake failure" in ch.error


def test_pipeline_stops_after_first_failed_chapter(tmp_path):
    en_dir = tmp_path / "en_chapters"
    cn_dir = tmp_path / "cn_chapters"
    en_dir.mkdir(parents=True)
    cn_dir.mkdir(parents=True)

    chapters = []
    for i in range(1, 3):
        en_file = en_dir / f"chapter_{i:03d}_en.txt"
        en_file.write_text(f"Chapter {i} text.", encoding="utf-8")
        chapters.append(
            ManifestChapter(
                index=i,
                title=f"Ch {i}",
                en_path=str(en_file),
                cn_path=expected_cn_path_for_en_path(str(en_file), str(cn_dir)),
                source_sha256="dummy_sha",
                translation_status=TRANSLATION_STATUS_PENDING,
            )
        )

    manifest = TranslationManifest(source_file=str(tmp_path / "input.txt"), chapters=chapters)
    config = _make_minimal_config(tmp_path)
    client = FailFirstClient()

    with pytest.raises(TranslationPipelineStoppedError):
        run_translation_pipeline(config, client, manifest, max_chapters=0)

    assert client.calls == 1
    assert manifest.chapters[0].translation_status == TRANSLATION_STATUS_FAILED
    assert manifest.chapters[1].translation_status == TRANSLATION_STATUS_PENDING


def test_resume_after_failed_batch(tmp_path):
    en_dir = tmp_path / "en_chapters"
    cn_dir = tmp_path / "cn_chapters"
    en_dir.mkdir(parents=True)
    cn_dir.mkdir(parents=True)

    chapter_file = en_dir / "chapter_001_en.txt"
    chapter_file.write_text("Para one.\n\nPara two.\n\nPara three.", encoding="utf-8")
    cn_path = expected_cn_path_for_en_path(str(chapter_file), str(cn_dir))

    manifest = TranslationManifest(
        source_file=str(tmp_path / "input.txt"),
        chapters=[
            ManifestChapter(
                index=1,
                title="Test Chapter",
                en_path=str(chapter_file),
                cn_path=cn_path,
                source_sha256="dummy_sha",
                translation_status=TRANSLATION_STATUS_PENDING,
            ),
        ],
    )

    config = AppConfig(
        paths=PathsConfig(
            input_file=str(tmp_path / "input.txt"),
            en_chapters_dir=str(en_dir),
            cn_chapters_dir=str(cn_dir),
            manifest_file=str(tmp_path / "manifest.json"),
        ),
        chunking=ChunkingConfig(
            initial_paragraphs_per_batch=1,
            min_paragraphs_per_batch=1,
            overflow_backoff_factor=0.5,
        ),
        translation=TranslationConfig(),
    )

    client = FailOnSecondBatchClient()

    with pytest.raises(TranslationPipelineStoppedError):
        run_translation_pipeline(config, client, manifest, max_chapters=1)

    assert manifest.chapters[0].translated_paragraph_count == 1
    resume_path = Path(expected_resume_state_path_for_cn_path(cn_path))
    assert resume_path.exists()

    client2 = SuccessClient()
    results = run_translation_pipeline(config, client2, manifest, chapter_index=1)

    assert len(results) == 1
    assert manifest.chapters[0].translation_status == TRANSLATION_STATUS_DONE
    assert Path(cn_path).parent == cn_dir
    assert Path(cn_path).exists()
    assert client.calls == 2


def test_translate_specific_chapter_only(tmp_path):
    en_dir = tmp_path / "en_chapters"
    cn_dir = tmp_path / "cn_chapters"
    en_dir.mkdir(parents=True)
    cn_dir.mkdir(parents=True)

    statuses = [
        TRANSLATION_STATUS_DONE,
        TRANSLATION_STATUS_FAILED,
        TRANSLATION_STATUS_PENDING,
        TRANSLATION_STATUS_PENDING,
    ]

    chapters = []
    for i in range(1, 5):
        en_file = en_dir / f"chapter_{i:03d}_en.txt"
        en_file.write_text(f"Chapter {i} text.", encoding="utf-8")
        chapters.append(
            ManifestChapter(
                index=i,
                title=f"Ch {i}",
                en_path=str(en_file),
                cn_path=expected_cn_path_for_en_path(str(en_file), str(cn_dir)),
                source_sha256="dummy_sha",
                translation_status=statuses[i - 1],
            )
        )

    manifest = TranslationManifest(source_file=str(tmp_path / "input.txt"), chapters=chapters)
    config = _make_minimal_config(tmp_path)
    client = SuccessClient()

    results = run_translation_pipeline(config, client, manifest, chapter_index=4)

    assert len(results) == 1
    assert results[0].chapter_index == 4
    assert manifest.chapters[1].translation_status == TRANSLATION_STATUS_FAILED
    assert manifest.chapters[2].translation_status == TRANSLATION_STATUS_PENDING
    assert manifest.chapters[3].translation_status == TRANSLATION_STATUS_DONE


def test_paragraph_batch_reduces_on_context_overflow_and_succeeds(tmp_path):
    en_dir = tmp_path / "en_chapters"
    cn_dir = tmp_path / "cn_chapters"
    en_dir.mkdir(parents=True)
    cn_dir.mkdir(parents=True)
    chapter_file = en_dir / "chapter_001_en.txt"
    chapter_file.write_text("Para one.\n\nPara two.\n\nPara three.", encoding="utf-8")
    cn_path = expected_cn_path_for_en_path(str(chapter_file), str(cn_dir))

    manifest = TranslationManifest(
        source_file=str(tmp_path / "input.txt"),
        chapters=[
            ManifestChapter(
                index=1,
                title="Test Chapter",
                en_path=str(chapter_file),
                cn_path=cn_path,
                source_sha256="dummy_sha",
                translation_status=TRANSLATION_STATUS_PENDING,
            ),
        ],
    )

    config = AppConfig(
        paths=PathsConfig(
            input_file=str(tmp_path / "input.txt"),
            en_chapters_dir=str(en_dir),
            cn_chapters_dir=str(cn_dir),
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
    assert Path(cn_path).exists()
    assert Path(cn_path).parent == cn_dir


def test_single_paragraph_context_overflow_fails_without_splitting(tmp_path):
    en_dir = tmp_path / "en_chapters"
    cn_dir = tmp_path / "cn_chapters"
    en_dir.mkdir(parents=True)
    cn_dir.mkdir(parents=True)
    chapter_file = en_dir / "chapter_001_en.txt"
    chapter_file.write_text("word " * 10000, encoding="utf-8")
    cn_path = expected_cn_path_for_en_path(str(chapter_file), str(cn_dir))

    manifest = TranslationManifest(
        source_file=str(tmp_path / "input.txt"),
        chapters=[
            ManifestChapter(
                index=1,
                title="Test Chapter",
                en_path=str(chapter_file),
                cn_path=cn_path,
                source_sha256="dummy_sha",
                translation_status=TRANSLATION_STATUS_PENDING,
            ),
        ],
    )

    config = AppConfig(
        paths=PathsConfig(
            input_file=str(tmp_path / "input.txt"),
            en_chapters_dir=str(en_dir),
            cn_chapters_dir=str(cn_dir),
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

    with pytest.raises(TranslationPipelineStoppedError):
        run_translation_pipeline(config, client, manifest, max_chapters=1)

    assert client.calls == 1
    assert manifest.chapters[0].translation_status == TRANSLATION_STATUS_FAILED
    assert "单个段落超过 LM Studio 当前上下文能力" in manifest.chapters[0].error
    assert "paragraph_index=0" in manifest.chapters[0].error
    assert not Path(cn_path).exists()
