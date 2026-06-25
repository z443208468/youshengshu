import wave
from dataclasses import dataclass
from pathlib import Path

from .audio_merge import merge_wav_files
from .config import TtsAppConfig
from .manifest import (
    SEGMENT_STATUS_DONE,
    SEGMENT_STATUS_FAILED,
    SEGMENT_STATUS_IN_PROGRESS,
    SEGMENT_STATUS_PENDING,
    TTS_STATUS_DONE,
    TTS_STATUS_FAILED,
    TTS_STATUS_IN_PROGRESS,
    TTS_STATUS_SEGMENTED,
    TtsChapter,
    TtsManifest,
    TtsSegment,
    sha256_text,
)
from .segment_store import load_segments, save_segments


@dataclass
class WavValidationResult:
    ok: bool
    reason: str | None
    channels: int | None = None
    sample_width: int | None = None
    sample_rate: int | None = None
    frames: int | None = None
    duration_ms: int | None = None


@dataclass
class ResumeRecoveryReport:
    chapter_index: int
    recovered_done_segments: int = 0
    reset_segments: int = 0
    removed_tmp_files: int = 0
    merged_chapter: bool = False
    recovered_chapter_done: bool = False


def expected_segment_wav_path(
    config: TtsAppConfig, chapter: TtsChapter, segment: TtsSegment
) -> Path:
    return (
        Path(config.paths.output_dir)
        / "wav_segments"
        / f"chapter_{chapter.index:03d}"
        / f"seg_{segment.segment_index:06d}.wav"
    )


def expected_chapter_wav_path(config: TtsAppConfig, chapter: TtsChapter) -> Path:
    return Path(config.paths.output_dir) / "chapters" / f"chapter_{chapter.index:03d}.wav"


def tmp_path_for_final(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".tmp")


def validate_wav_file(path: Path, expected_sample_rate: int) -> WavValidationResult:
    if not path.exists():
        return WavValidationResult(ok=False, reason="missing")

    if not path.is_file():
        return WavValidationResult(ok=False, reason="not_file")

    try:
        with wave.open(str(path), "rb") as wav:
            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            sample_rate = wav.getframerate()
            frames = wav.getnframes()
    except Exception as exc:
        return WavValidationResult(ok=False, reason=f"invalid_wav:{exc}")

    if channels != 1:
        return WavValidationResult(
            ok=False,
            reason=f"unexpected_channels:{channels}",
            channels=channels,
            sample_width=sample_width,
            sample_rate=sample_rate,
            frames=frames,
        )

    if sample_width != 2:
        return WavValidationResult(
            ok=False,
            reason=f"unexpected_sample_width:{sample_width}",
            channels=channels,
            sample_width=sample_width,
            sample_rate=sample_rate,
            frames=frames,
        )

    if sample_rate != expected_sample_rate:
        return WavValidationResult(
            ok=False,
            reason=f"unexpected_sample_rate:{sample_rate}",
            channels=channels,
            sample_width=sample_width,
            sample_rate=sample_rate,
            frames=frames,
        )

    if frames <= 0:
        return WavValidationResult(
            ok=False,
            reason="empty_audio",
            channels=channels,
            sample_width=sample_width,
            sample_rate=sample_rate,
            frames=frames,
        )

    duration_ms = int((frames * 1000) / sample_rate)

    return WavValidationResult(
        ok=True,
        reason=None,
        channels=channels,
        sample_width=sample_width,
        sample_rate=sample_rate,
        frames=frames,
        duration_ms=duration_ms,
    )


def cleanup_tmp_file_for_path(path: Path) -> bool:
    tmp = path.with_suffix(path.suffix + ".tmp")
    if tmp.exists():
        tmp.unlink()
        return True
    return False


def cleanup_uncommitted_tmp(path: Path) -> bool:
    return cleanup_tmp_file_for_path(path)


def cleanup_manifest_and_segments_tmp(
    manifest_path: Path,
    chapter: TtsChapter,
) -> int:
    removed = 0

    if cleanup_tmp_file_for_path(manifest_path):
        removed += 1

    if chapter.segments_path:
        segments_path = Path(chapter.segments_path)
        if cleanup_tmp_file_for_path(segments_path):
            removed += 1

    return removed


def cleanup_chapter_tmp_outputs(
    config: TtsAppConfig,
    chapter: TtsChapter,
    segments: list[TtsSegment],
) -> int:
    removed = 0

    for segment in segments:
        final_path = expected_segment_wav_path(config, chapter, segment)
        if cleanup_uncommitted_tmp(final_path):
            removed += 1

    chapter_wav = expected_chapter_wav_path(config, chapter)
    if cleanup_uncommitted_tmp(chapter_wav):
        removed += 1

    return removed


def reconcile_segment_for_resume(
    config: TtsAppConfig,
    chapter: TtsChapter,
    segment: TtsSegment,
    retry_failed: bool,
) -> tuple[bool, bool]:
    changed = False
    recovered_done = False

    current_hash = sha256_text(segment.text)
    deterministic_wav = expected_segment_wav_path(config, chapter, segment)
    expected_sample_rate = config.cosyvoice.sample_rate

    if segment.text_sha256 != current_hash:
        segment.text_sha256 = current_hash
        segment.status = SEGMENT_STATUS_PENDING
        segment.wav_path = None
        segment.duration_ms = None
        segment.error = "text hash changed; segment reset for regeneration"
        return True, False

    wav_result = validate_wav_file(deterministic_wav, expected_sample_rate)

    if wav_result.ok:
        if (
            segment.status != SEGMENT_STATUS_DONE
            or segment.wav_path != str(deterministic_wav)
            or segment.duration_ms != wav_result.duration_ms
            or segment.error is not None
        ):
            segment.status = SEGMENT_STATUS_DONE
            segment.wav_path = str(deterministic_wav)
            segment.duration_ms = wav_result.duration_ms
            segment.error = None
            changed = True
            recovered_done = True

        return changed, recovered_done

    if segment.status == SEGMENT_STATUS_DONE:
        segment.status = SEGMENT_STATUS_PENDING
        segment.wav_path = None
        segment.duration_ms = None
        segment.error = f"done segment wav invalid: {wav_result.reason}"
        return True, False

    if segment.status == SEGMENT_STATUS_IN_PROGRESS:
        segment.status = SEGMENT_STATUS_PENDING
        segment.wav_path = None
        segment.duration_ms = None
        segment.error = "previous run interrupted during segment synthesis"
        return True, False

    if segment.status == SEGMENT_STATUS_FAILED and retry_failed:
        segment.status = SEGMENT_STATUS_PENDING
        segment.wav_path = None
        segment.duration_ms = None
        segment.error = None
        return True, False

    return changed, recovered_done


def recompute_chapter_counts(chapter: TtsChapter, segments: list[TtsSegment]) -> None:
    chapter.segment_count = len(segments)
    chapter.done_segment_count = sum(
        1 for item in segments if item.status == SEGMENT_STATUS_DONE
    )
    chapter.failed_segment_count = sum(
        1 for item in segments if item.status == SEGMENT_STATUS_FAILED
    )


def reconcile_chapter_for_resume(
    config: TtsAppConfig,
    chapter: TtsChapter,
    segments: list[TtsSegment],
    retry_failed: bool,
    merge_when_complete: bool,
) -> ResumeRecoveryReport:
    report = ResumeRecoveryReport(chapter_index=chapter.index)

    report.removed_tmp_files += cleanup_chapter_tmp_outputs(config, chapter, segments)

    changed = False
    for segment in segments:
        segment_changed, recovered_done = reconcile_segment_for_resume(
            config=config,
            chapter=chapter,
            segment=segment,
            retry_failed=retry_failed,
        )
        if segment_changed:
            changed = True
        if recovered_done:
            report.recovered_done_segments += 1

    recompute_chapter_counts(chapter, segments)

    chapter_wav_path = expected_chapter_wav_path(config, chapter)
    chapter_wav_result = validate_wav_file(chapter_wav_path, config.audio.sample_rate)

    all_segments_done = len(segments) > 0 and all(
        segment.status == SEGMENT_STATUS_DONE for segment in segments
    )

    if all_segments_done:
        if not chapter_wav_result.ok and merge_when_complete:
            wav_inputs = [Path(segment.wav_path) for segment in segments if segment.wav_path]
            merge_wav_files(wav_inputs, chapter_wav_path)
            report.merged_chapter = True
            chapter_wav_result = validate_wav_file(chapter_wav_path, config.audio.sample_rate)
            if not chapter_wav_result.ok:
                raise RuntimeError(
                    f"chapter wav invalid after merge: chapter={chapter.index}; "
                    f"reason={chapter_wav_result.reason}"
                )

        if chapter_wav_result.ok:
            if (
                chapter.status != TTS_STATUS_DONE
                or chapter.chapter_wav_path != str(chapter_wav_path)
                or chapter.failed_segment_count != 0
                or chapter.error is not None
            ):
                chapter.status = TTS_STATUS_DONE
                chapter.chapter_wav_path = str(chapter_wav_path)
                chapter.failed_segment_count = 0
                chapter.done_segment_count = len(segments)
                chapter.error = None
                changed = True
                report.recovered_chapter_done = True
        else:
            chapter.status = TTS_STATUS_SEGMENTED
            chapter.chapter_wav_path = None
            chapter.error = (
                f"all segments done but chapter wav missing: {chapter_wav_result.reason}"
            )
            changed = True

    else:
        if retry_failed:
            chapter.status = TTS_STATUS_IN_PROGRESS
            chapter.error = None
            changed = True
        else:
            if chapter.failed_segment_count > 0:
                chapter.status = TTS_STATUS_FAILED
            elif chapter.done_segment_count > 0:
                chapter.status = TTS_STATUS_IN_PROGRESS
            else:
                chapter.status = TTS_STATUS_SEGMENTED
            changed = True

    if changed:
        report.reset_segments = sum(
            1 for item in segments if item.status == SEGMENT_STATUS_PENDING
        )

    return report


def recover_manifest_state(
    config: TtsAppConfig,
    manifest: TtsManifest,
    manifest_path: Path,
    retry_failed: bool,
    merge_when_complete: bool,
) -> list[ResumeRecoveryReport]:
    reports: list[ResumeRecoveryReport] = []

    for chapter in manifest.chapters:
        removed_json_tmp = cleanup_manifest_and_segments_tmp(
            manifest_path=manifest_path,
            chapter=chapter,
        )

        if not chapter.segments_path:
            continue

        segments_path = Path(chapter.segments_path)
        if not segments_path.exists():
            continue

        segments = load_segments(segments_path)

        report = reconcile_chapter_for_resume(
            config=config,
            chapter=chapter,
            segments=segments,
            retry_failed=retry_failed,
            merge_when_complete=merge_when_complete,
        )

        report.removed_tmp_files += removed_json_tmp

        save_segments(segments_path, segments)
        reports.append(report)

    manifest.save(manifest_path)
    return reports
