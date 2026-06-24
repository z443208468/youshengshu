import json
import re
from dataclasses import asdict
from pathlib import Path

from .audio_merge import merge_wav_files
from .config import TtsAppConfig
from .manifest import (
    SEGMENT_STATUS_DONE,
    SEGMENT_STATUS_FAILED,
    SEGMENT_STATUS_PENDING,
    TTS_STATUS_DONE,
    TTS_STATUS_FAILED,
    TTS_STATUS_IN_PROGRESS,
    TTS_STATUS_SEGMENTED,
    TtsChapter,
    TtsManifest,
    TtsSegment,
    load_manifest,
    now_iso,
    sha256_text,
)
from .providers.base import TtsProvider
from .text_segmenter import split_text_to_segments


def chapter_sort_key(path: Path) -> tuple[int, str]:
    match = re.search(r"chapter_(\d+)_cn\.txt$", path.name)
    if match:
        return (int(match.group(1)), path.name)
    return (10**9, path.name)


def create_project(config: TtsAppConfig) -> TtsManifest:
    source_mode = config.paths.source_mode

    if source_mode == "txt_file":
        chapters = discover_txt_file(config.paths.source_path)
    elif source_mode == "cn_chapters_dir":
        chapters = discover_cn_chapters_dir(config.paths.source_path)
    else:
        raise ValueError(f"不支持的 source_mode: {source_mode}")

    manifest_path = Path(config.paths.manifest_file)
    project_id = manifest_path.parent.name

    manifest = TtsManifest(
        project_id=project_id,
        source_mode=source_mode,
        source_path=config.paths.source_path,
        output_dir=config.paths.output_dir,
        created_at=now_iso(),
        updated_at=now_iso(),
        chapters=chapters,
    )
    manifest.save(manifest_path)
    return manifest


def discover_txt_file(source_path: str) -> list[TtsChapter]:
    path = Path(source_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"TXT 文件不存在: {path}")

    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError(f"TXT 文件为空: {path}")

    return [
        TtsChapter(
            index=1,
            title=path.stem,
            source_path=str(path),
            source_sha256=sha256_text(text),
        )
    ]


def discover_cn_chapters_dir(source_path: str) -> list[TtsChapter]:
    root = Path(source_path)
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"中文章节目录不存在: {root}")

    files = sorted(
        [p for p in root.glob("*.txt") if p.is_file()],
        key=chapter_sort_key,
    )

    if not files:
        raise ValueError(f"中文章节目录没有 txt 文件: {root}")

    chapters = []
    for i, path in enumerate(files, start=1):
        text = path.read_text(encoding="utf-8")
        chapters.append(
            TtsChapter(
                index=i,
                title=path.stem,
                source_path=str(path),
                source_sha256=sha256_text(text),
            )
        )
    return chapters


def segment_chapter(chapter: TtsChapter, config: TtsAppConfig) -> list[TtsSegment]:
    text = Path(chapter.source_path).read_text(encoding="utf-8")
    segment_texts = split_text_to_segments(text, config.segmentation)

    segments: list[TtsSegment] = []
    for segment_index, segment_text in enumerate(segment_texts, start=1):
        segments.append(
            TtsSegment(
                chapter_index=chapter.index,
                segment_index=segment_index,
                text=segment_text,
                text_sha256=sha256_text(segment_text),
            )
        )

    segments_path = (
        Path(config.paths.output_dir) / "segments" / f"chapter_{chapter.index:03d}.json"
    )
    save_segments(segments_path, segments)
    chapter.segments_path = str(segments_path)
    chapter.segment_count = len(segments)
    chapter.done_segment_count = 0
    chapter.failed_segment_count = 0
    chapter.status = TTS_STATUS_SEGMENTED
    chapter.error = None
    return segments


class TtsPipelineStoppedError(RuntimeError):
    pass


def get_chapter_or_raise(manifest: TtsManifest, chapter_index: int) -> TtsChapter:
    for chapter in manifest.chapters:
        if chapter.index == chapter_index:
            return chapter
    raise ValueError(f"章节不存在: {chapter_index}")


def load_segments(path: Path) -> list[TtsSegment]:
    if not path.exists():
        raise FileNotFoundError(f"TTS segments 文件不存在: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    segments: list[TtsSegment] = []

    for item in data:
        segments.append(
            TtsSegment(
                chapter_index=int(item["chapter_index"]),
                segment_index=int(item["segment_index"]),
                text=str(item["text"]),
                text_sha256=str(item["text_sha256"]),
                status=str(item.get("status", SEGMENT_STATUS_PENDING)),
                wav_path=item.get("wav_path"),
                duration_ms=item.get("duration_ms"),
                error=item.get("error"),
            )
        )

    return segments


def save_segments(path: Path, segments: list[TtsSegment]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps([asdict(segment) for segment in segments], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp.replace(path)


def ensure_chapter_segments(
    chapter: TtsChapter,
    config: TtsAppConfig,
    manifest: TtsManifest,
    manifest_path: Path,
) -> list[TtsSegment]:
    if chapter.segments_path:
        segments_path = Path(chapter.segments_path)
        if segments_path.exists():
            return load_segments(segments_path)

    segments = segment_chapter(chapter, config)
    chapter.segment_count = len(segments)
    chapter.done_segment_count = 0
    chapter.failed_segment_count = 0
    chapter.status = TTS_STATUS_SEGMENTED
    manifest.save(manifest_path)
    return segments


def synthesize_chapter(
    chapter_index: int,
    config: TtsAppConfig,
    manifest: TtsManifest,
    manifest_path: Path,
    provider: TtsProvider,
) -> None:
    chapter = get_chapter_or_raise(manifest, chapter_index)
    segments = ensure_chapter_segments(chapter, config, manifest, manifest_path)

    if not chapter.segments_path:
        raise ValueError(f"章节缺少 segments_path: {chapter.index}")

    segments_path = Path(chapter.segments_path)
    wav_root = Path(config.paths.output_dir) / "wav_segments" / f"chapter_{chapter.index:03d}"
    chapter_wav_path = Path(config.paths.output_dir) / "chapters" / f"chapter_{chapter.index:03d}.wav"

    chapter.status = TTS_STATUS_IN_PROGRESS
    chapter.error = None
    manifest.save(manifest_path)

    for segment in segments:
        segment_wav_path = wav_root / f"seg_{segment.segment_index:06d}.wav"

        if (
            segment.status == SEGMENT_STATUS_DONE
            and segment.wav_path
            and Path(segment.wav_path).exists()
            and segment.text_sha256 == sha256_text(segment.text)
        ):
            continue

        try:
            segment.status = SEGMENT_STATUS_PENDING
            segment.error = None
            save_segments(segments_path, segments)

            provider.synthesize_to_file(segment.text, segment_wav_path)

            segment.status = SEGMENT_STATUS_DONE
            segment.wav_path = str(segment_wav_path)
            segment.error = None
            save_segments(segments_path, segments)

        except Exception as exc:
            segment.status = SEGMENT_STATUS_FAILED
            segment.error = str(exc)

            chapter.status = TTS_STATUS_FAILED
            chapter.error = str(exc)
            chapter.done_segment_count = sum(
                1 for item in segments if item.status == SEGMENT_STATUS_DONE
            )
            chapter.failed_segment_count = sum(
                1 for item in segments if item.status == SEGMENT_STATUS_FAILED
            )

            save_segments(segments_path, segments)
            manifest.save(manifest_path)

            raise TtsPipelineStoppedError(
                f"第 {chapter.index} 章第 {segment.segment_index} 段生成失败: {exc}"
            ) from exc

    wav_inputs = [Path(segment.wav_path) for segment in segments if segment.wav_path]

    if len(wav_inputs) != len(segments):
        raise TtsPipelineStoppedError(
            f"第 {chapter.index} 章存在缺失 wav 的片段，不能合并。"
        )

    merge_wav_files(wav_inputs, chapter_wav_path)

    chapter.status = TTS_STATUS_DONE
    chapter.done_segment_count = len(segments)
    chapter.failed_segment_count = 0
    chapter.chapter_wav_path = str(chapter_wav_path)
    chapter.error = None

    save_segments(segments_path, segments)
    manifest.save(manifest_path)


def find_next_chapter_index(manifest: TtsManifest) -> int | None:
    for chapter in manifest.chapters:
        if chapter.status != TTS_STATUS_DONE:
            return chapter.index
    return None
