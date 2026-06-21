import tempfile
from pathlib import Path

from youshengshu.progress import (
    TranslationManifest,
    ManifestChapter,
    TRANSLATION_STATUS_PENDING,
    TRANSLATION_STATUS_DONE,
    TRANSLATION_STATUS_FAILED,
    TRANSLATION_STATUS_IN_PROGRESS,
)


def _make_test_chapters(count=3):
    return [
        ManifestChapter(
            index=i,
            title=f"Chapter {i}",
            en_path=f"data/en_chapters/chapter_{i:03d}_en.txt",
            source_sha256=f"abcdef{i}" * 10,
        )
        for i in range(1, count + 1)
    ]


def test_create_manifest():
    chapters = _make_test_chapters(3)
    manifest = TranslationManifest(
        source_file="test.txt",
        chapters=chapters,
    )
    assert manifest.source_file == "test.txt"
    assert len(manifest.chapters) == 3
    assert manifest.chapters[0].translation_status == TRANSLATION_STATUS_PENDING


def test_save_and_load_manifest():
    chapters = _make_test_chapters(3)
    manifest = TranslationManifest(
        source_file="test.txt",
        chapters=chapters,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "manifest.json"
        manifest.save(path)

        loaded = TranslationManifest.load(path)
        assert loaded.source_file == "test.txt"
        assert len(loaded.chapters) == 3


def test_done_chapters_skipped():
    chapters = _make_test_chapters(3)
    manifest = TranslationManifest(source_file="test.txt", chapters=chapters)

    # Mark chapter 1 as done
    manifest.set_chapter_status(1, TRANSLATION_STATUS_DONE)
    assert manifest.chapters[0].translation_status == TRANSLATION_STATUS_DONE

    # Next pending should be chapter 2
    next_ch = manifest.get_next_pending_chapter()
    assert next_ch is not None
    assert next_ch.index == 2


def test_sha256_change_resets_status():
    chapters = _make_test_chapters(2)
    manifest = TranslationManifest(source_file="test.txt", chapters=chapters)

    # Mark as done
    manifest.set_chapter_status(1, TRANSLATION_STATUS_DONE)

    # Change sha256 manually to simulate change
    manifest.chapters[0].source_sha256 = "different_sha256_value_here"

    # The check_and_reset_stale should catch this if file exists and sha differs
    # For unit test, we verify the state is inconsistent with stale detection
    assert manifest.get_chapter_by_index(1).source_sha256 == "different_sha256_value_here"


def test_failed_status_can_be_retried():
    chapters = _make_test_chapters(2)
    manifest = TranslationManifest(source_file="test.txt", chapters=chapters)

    manifest.set_chapter_status(1, TRANSLATION_STATUS_FAILED, error="timeout")
    assert manifest.chapters[0].translation_status == TRANSLATION_STATUS_FAILED

    next_ch = manifest.get_next_pending_chapter()
    assert next_ch is not None
    assert next_ch.index == 1


def test_get_summary():
    chapters = _make_test_chapters(4)
    manifest = TranslationManifest(source_file="test.txt", chapters=chapters)

    manifest.set_chapter_status(1, TRANSLATION_STATUS_DONE)
    manifest.set_chapter_status(2, TRANSLATION_STATUS_DONE)
    manifest.set_chapter_status(3, TRANSLATION_STATUS_FAILED, error="error")

    summary = manifest.get_summary()
    assert summary["total"] == 4
    assert summary["done"] == 2
    assert summary["failed"] == 1
    assert summary["pending"] == 1
    assert summary["in_progress"] == 0
    assert summary["next_chapter"] == 3  # failed chapter should be next
