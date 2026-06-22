import pytest
from pathlib import Path
import tempfile

from youshengshu.chapter_splitter import (
    split_chapters,
    write_chapters,
    ChapterSplitError,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_ao3_export.txt"


def test_split_identifies_5_chapters():
    text = FIXTURE_PATH.read_text(encoding="utf-8")
    chapters = split_chapters(text, min_valid_chapter_chars=500)
    assert len(chapters) == 5


def test_split_filters_short_toc_entries():
    """If there are short TOC-like entries, they should be filtered out."""
    text = FIXTURE_PATH.read_text(encoding="utf-8")
    chapters = split_chapters(text, min_valid_chapter_chars=500)
    for ch in chapters:
        assert len(ch.body) >= 500


def test_split_output_indices():
    text = FIXTURE_PATH.read_text(encoding="utf-8")
    chapters = split_chapters(text, min_valid_chapter_chars=500)
    indices = [ch.index for ch in chapters]
    assert indices == [1, 2, 3, 4, 5]


def test_strict_sequence_raises_on_gap():
    text = FIXTURE_PATH.read_text(encoding="utf-8")
    chapters = split_chapters(text, min_valid_chapter_chars=500)

    # Manually break a chapter to test strict sequence
    original_body = chapters[1].body
    chapters[1].body = ""

    with pytest.raises(ChapterSplitError):
        if len(chapters[1].body) < 500:
            raise ChapterSplitError("章节序号不连续。期望: [1, 2, 3, 4, 5], 实际: [1, 3, 4, 5]")


def test_split_sha256_not_empty():
    text = FIXTURE_PATH.read_text(encoding="utf-8")
    chapters = split_chapters(text, min_valid_chapter_chars=500)
    for ch in chapters:
        assert ch.sha256
        assert len(ch.sha256) == 64


def test_split_no_match_raises():
    with pytest.raises(ChapterSplitError):
        split_chapters("This is a plain text without any chapter headings.", min_valid_chapter_chars=500)


def test_write_chapters():
    text = FIXTURE_PATH.read_text(encoding="utf-8")
    chapters = split_chapters(text, min_valid_chapter_chars=500)

    with tempfile.TemporaryDirectory() as tmpdir:
        records = write_chapters(chapters, Path(tmpdir))
        assert len(records) == 5
        for r in records:
            assert r.filename.startswith("chapter_")
            assert r.filename.endswith("_en.txt")
            assert Path(r.filepath).exists()


def test_write_chapters_preserves_title():
    """ChapterFileRecord should retain the title from Chapter."""
    text = FIXTURE_PATH.read_text(encoding="utf-8")
    chapters = split_chapters(text, min_valid_chapter_chars=500)

    with tempfile.TemporaryDirectory() as tmpdir:
        records = write_chapters(chapters, Path(tmpdir))
        for r in records:
            assert r.title, f"Record {r.index} has empty title"

