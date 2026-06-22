import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from .exceptions import ChapterSplitError
from .text_utils import normalize_newlines

AO3_CHAPTER_HEADING_RE = re.compile(
    r"(?m)^Chapter\s+(\d+):\s+Chapter\s+\1:\s*(.+?)\s*$"
)


@dataclass
class Chapter:
    index: int
    title: str
    raw_heading: str
    body: str
    source_start: int
    source_end: int
    sha256: str


@dataclass
class ChapterFileRecord:
    index: int
    title: str
    filename: str
    filepath: str
    sha256: str


def split_chapters(
    source_text: str,
    min_valid_chapter_chars: int = 3000,
    strict_sequence: bool = True,
) -> list[Chapter]:
    """Split AO3-exported novel TXT into chapters."""

    text = normalize_newlines(source_text)

    candidates = list(AO3_CHAPTER_HEADING_RE.finditer(text))

    if not candidates:
        raise ChapterSplitError(
            "未找到 AO3 章节标题。"
            "当前只支持形如 'Chapter 1: Chapter 1: Greetings' 的导出格式。"
        )

    chapters: list[Chapter] = []

    for i, match in enumerate(candidates):
        start = match.start()
        end = candidates[i + 1].start() if i + 1 < len(candidates) else len(text)
        block_text = text[start:end].strip()
        body_length = len(block_text)

        if body_length < min_valid_chapter_chars:
            continue

        chapter = Chapter(
            index=int(match.group(1)),
            title=match.group(2).strip(),
            raw_heading=match.group(0).strip(),
            body=block_text,
            source_start=start,
            source_end=end,
            sha256=hashlib.sha256(block_text.encode("utf-8")).hexdigest(),
        )
        chapters.append(chapter)

    if not chapters:
        raise ChapterSplitError(
            "识别到章节标题，但没有任何章节正文超过 "
            f"min_valid_chapter_chars({min_valid_chapter_chars})。请检查导出文件。"
        )

    if strict_sequence:
        expected = list(range(1, len(chapters) + 1))
        actual = [ch.index for ch in chapters]
        if actual != expected:
            raise ChapterSplitError(
                f"章节序号不连续。期望: {expected}, 实际: {actual}"
            )

    return chapters


def write_chapters(
    chapters: list[Chapter],
    out_dir: Path,
) -> list[ChapterFileRecord]:
    """Write each chapter to a separate file in out_dir."""

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    records: list[ChapterFileRecord] = []

    for ch in chapters:
        filename = f"chapter_{ch.index:03d}_en.txt"
        filepath = out_dir / filename

        filepath.write_text(ch.body, encoding="utf-8")

        records.append(
            ChapterFileRecord(
                index=ch.index,
                title=ch.title,
                filename=filename,
                filepath=str(filepath),
                sha256=ch.sha256,
            )
        )

    return records
