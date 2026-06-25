import json
import wave
from dataclasses import asdict
from pathlib import Path

import pytest

from youshengshu_tts.config import (
    CosyVoiceHttpConfig,
    TtsAppConfig,
    TtsAudioConfig,
    TtsPathsConfig,
    TtsSegmentationConfig,
)
from youshengshu_tts.manifest import (
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
    load_manifest,
    now_iso,
    sha256_text,
)
from youshengshu_tts.pipeline import synthesize_chapter
from youshengshu_tts.providers.base import TtsProvider, TtsProviderResult
from youshengshu_tts.resume import (
    expected_segment_wav_path,
    reconcile_chapter_for_resume,
    recover_manifest_state,
)
from youshengshu_tts.segment_store import load_segments, save_segments


def write_test_wav(path: Path, sample_rate: int = 22050, frames: int = 1000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"\x00\x00" * frames)


def _make_config(tmp_path: Path) -> TtsAppConfig:
    output_dir = tmp_path / "audio_projects" / "default"
    return TtsAppConfig(
        paths=TtsPathsConfig(
            source_mode="txt_file",
            source_path=str(tmp_path / "source.txt"),
            output_dir=str(output_dir),
            manifest_file=str(output_dir / "audio_manifest.json"),
        ),
        segmentation=TtsSegmentationConfig(),
        cosyvoice=CosyVoiceHttpConfig(),
        audio=TtsAudioConfig(),
    )


def _make_chapter(index: int = 1) -> TtsChapter:
    return TtsChapter(
        index=index,
        title=f"chapter_{index:03d}",
        source_path="source.txt",
        source_sha256="sha",
        status=TTS_STATUS_SEGMENTED,
        segment_count=1,
        segments_path=None,
    )


def _make_segment(
    text: str = "测试片段",
    status: str = SEGMENT_STATUS_PENDING,
    chapter_index: int = 1,
    segment_index: int = 1,
) -> TtsSegment:
    return TtsSegment(
        chapter_index=chapter_index,
        segment_index=segment_index,
        text=text,
        text_sha256=sha256_text(text),
        status=status,
    )


def _setup_manifest_with_segments(
    tmp_path: Path,
    segments: list[TtsSegment],
    chapter: TtsChapter | None = None,
) -> tuple[TtsAppConfig, TtsManifest, Path, TtsChapter, Path]:
    config = _make_config(tmp_path)
    output_dir = Path(config.paths.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    chapter = chapter or _make_chapter()
    segments_path = output_dir / "segments" / "chapter_001.json"
    save_segments(segments_path, segments)
    chapter.segments_path = str(segments_path)

    manifest_path = Path(config.paths.manifest_file)
    manifest = TtsManifest(
        project_id="default",
        source_mode="txt_file",
        source_path="source.txt",
        output_dir=str(output_dir),
        created_at=now_iso(),
        updated_at=now_iso(),
        chapters=[chapter],
    )
    manifest.save(manifest_path)
    return config, manifest, manifest_path, chapter, segments_path


def test_resume_recovers_orphan_segment_wav_as_done(tmp_path: Path):
    segment = _make_segment(status=SEGMENT_STATUS_PENDING)
    config, _manifest, _manifest_path, chapter, segments_path = _setup_manifest_with_segments(
        tmp_path, [segment]
    )
    wav_path = expected_segment_wav_path(config, chapter, segment)
    write_test_wav(wav_path, sample_rate=config.cosyvoice.sample_rate)

    segments = load_segments(segments_path)
    reconcile_chapter_for_resume(
        config=config,
        chapter=chapter,
        segments=segments,
        retry_failed=True,
        merge_when_complete=False,
    )

    assert segments[0].status == SEGMENT_STATUS_DONE
    assert segments[0].wav_path == str(wav_path)
    assert segments[0].duration_ms is not None


def test_resume_resets_interrupted_in_progress_without_wav(tmp_path: Path):
    segment = _make_segment(status=SEGMENT_STATUS_IN_PROGRESS)
    config, _manifest, _manifest_path, chapter, segments_path = _setup_manifest_with_segments(
        tmp_path, [segment]
    )

    segments = load_segments(segments_path)
    reconcile_chapter_for_resume(
        config=config,
        chapter=chapter,
        segments=segments,
        retry_failed=True,
        merge_when_complete=False,
    )

    assert segments[0].status == SEGMENT_STATUS_PENDING
    assert segments[0].error == "previous run interrupted during segment synthesis"


def test_resume_retries_failed_segment_when_retry_failed_true(tmp_path: Path):
    segment = _make_segment(status=SEGMENT_STATUS_FAILED)
    segment.error = "boom"
    config, _manifest, _manifest_path, chapter, segments_path = _setup_manifest_with_segments(
        tmp_path, [segment]
    )

    segments = load_segments(segments_path)
    reconcile_chapter_for_resume(
        config=config,
        chapter=chapter,
        segments=segments,
        retry_failed=True,
        merge_when_complete=False,
    )

    assert segments[0].status == SEGMENT_STATUS_PENDING
    assert segments[0].error is None


def test_status_recovery_does_not_reset_failed_when_retry_failed_false(tmp_path: Path):
    segment = _make_segment(status=SEGMENT_STATUS_FAILED)
    segment.error = "boom"
    config, manifest, manifest_path, _chapter, _segments_path = _setup_manifest_with_segments(
        tmp_path, [segment]
    )

    recover_manifest_state(
        config=config,
        manifest=manifest,
        manifest_path=manifest_path,
        retry_failed=False,
        merge_when_complete=False,
    )

    manifest = load_manifest(manifest_path)
    segments = load_segments(Path(manifest.chapters[0].segments_path))
    assert segments[0].status == SEGMENT_STATUS_FAILED


def test_resume_resets_done_segment_with_corrupt_wav(tmp_path: Path):
    segment = _make_segment(status=SEGMENT_STATUS_DONE)
    config, _manifest, _manifest_path, chapter, segments_path = _setup_manifest_with_segments(
        tmp_path, [segment]
    )
    wav_path = expected_segment_wav_path(config, chapter, segment)
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    wav_path.write_text("not a wav", encoding="utf-8")
    segment.wav_path = str(wav_path)
    save_segments(segments_path, [segment])

    segments = load_segments(segments_path)
    reconcile_chapter_for_resume(
        config=config,
        chapter=chapter,
        segments=segments,
        retry_failed=True,
        merge_when_complete=False,
    )

    assert segments[0].status == SEGMENT_STATUS_PENDING
    assert "done segment wav invalid" in (segments[0].error or "")


def test_resume_merges_chapter_when_all_segments_done(tmp_path: Path):
    seg1 = _make_segment("片段一", SEGMENT_STATUS_DONE, segment_index=1)
    seg2 = _make_segment("片段二", SEGMENT_STATUS_DONE, segment_index=2)
    config, _manifest, _manifest_path, chapter, segments_path = _setup_manifest_with_segments(
        tmp_path, [seg1, seg2]
    )
    chapter.segment_count = 2
    for segment in [seg1, seg2]:
        wav_path = expected_segment_wav_path(config, chapter, segment)
        write_test_wav(wav_path, sample_rate=config.cosyvoice.sample_rate)
        segment.wav_path = str(wav_path)
    save_segments(segments_path, [seg1, seg2])

    segments = load_segments(segments_path)
    reconcile_chapter_for_resume(
        config=config,
        chapter=chapter,
        segments=segments,
        retry_failed=False,
        merge_when_complete=True,
    )

    assert chapter.status == TTS_STATUS_DONE
    assert chapter.chapter_wav_path
    assert Path(chapter.chapter_wav_path).exists()


def test_resume_marks_chapter_done_when_chapter_wav_exists(tmp_path: Path):
    segment = _make_segment(status=SEGMENT_STATUS_DONE)
    config, _manifest, _manifest_path, chapter, segments_path = _setup_manifest_with_segments(
        tmp_path, [segment]
    )
    wav_path = expected_segment_wav_path(config, chapter, segment)
    write_test_wav(wav_path, sample_rate=config.cosyvoice.sample_rate)
    segment.wav_path = str(wav_path)
    save_segments(segments_path, [segment])

    chapter_wav = Path(config.paths.output_dir) / "chapters" / "chapter_001.wav"
    write_test_wav(chapter_wav, sample_rate=config.audio.sample_rate)
    chapter.status = TTS_STATUS_IN_PROGRESS

    segments = load_segments(segments_path)
    reconcile_chapter_for_resume(
        config=config,
        chapter=chapter,
        segments=segments,
        retry_failed=False,
        merge_when_complete=True,
    )

    assert chapter.status == TTS_STATUS_DONE
    assert chapter.chapter_wav_path == str(chapter_wav)


def test_resume_removes_uncommitted_tmp_files(tmp_path: Path):
    segment = _make_segment(status=SEGMENT_STATUS_PENDING)
    config, _manifest, _manifest_path, chapter, segments_path = _setup_manifest_with_segments(
        tmp_path, [segment]
    )
    seg_wav = expected_segment_wav_path(config, chapter, segment)
    write_test_wav(seg_wav, sample_rate=config.cosyvoice.sample_rate)
    seg_tmp = seg_wav.with_suffix(seg_wav.suffix + ".tmp")
    seg_tmp.write_bytes(b"partial")

    chapter_wav = Path(config.paths.output_dir) / "chapters" / "chapter_001.wav"
    chapter_tmp = chapter_wav.with_suffix(chapter_wav.suffix + ".tmp")
    chapter_tmp.parent.mkdir(parents=True, exist_ok=True)
    chapter_tmp.write_bytes(b"partial")

    segments = load_segments(segments_path)
    report = reconcile_chapter_for_resume(
        config=config,
        chapter=chapter,
        segments=segments,
        retry_failed=True,
        merge_when_complete=False,
    )

    assert not seg_tmp.exists()
    assert not chapter_tmp.exists()
    assert seg_wav.exists()
    assert report.removed_tmp_files >= 2


class CountingProvider(TtsProvider):
    def __init__(self, sample_rate: int = 22050):
        self.calls: list[tuple[str, Path]] = []
        self.sample_rate = sample_rate

    def synthesize_to_file(self, text: str, output_path: Path) -> TtsProviderResult:
        self.calls.append((text, output_path))
        write_test_wav(output_path, sample_rate=self.sample_rate)
        return TtsProviderResult(output_path=str(output_path), sample_rate=self.sample_rate)


def test_synthesize_chapter_skips_recovered_done_segments(tmp_path: Path):
    seg1 = _make_segment("片段一", SEGMENT_STATUS_PENDING, segment_index=1)
    seg2 = _make_segment("片段二", SEGMENT_STATUS_PENDING, segment_index=2)
    config, manifest, manifest_path, chapter, segments_path = _setup_manifest_with_segments(
        tmp_path, [seg1, seg2]
    )
    chapter.segment_count = 2
    wav1 = expected_segment_wav_path(config, chapter, seg1)
    write_test_wav(wav1, sample_rate=config.cosyvoice.sample_rate)

    provider = CountingProvider(sample_rate=config.cosyvoice.sample_rate)
    synthesize_chapter(1, config, manifest, manifest_path, provider)

    assert len(provider.calls) == 1
    segments = load_segments(segments_path)
    assert all(item.status == SEGMENT_STATUS_DONE for item in segments)
    manifest = load_manifest(manifest_path)
    assert manifest.chapters[0].status == TTS_STATUS_DONE


def test_synthesize_all_resume_failed_chapter(tmp_path: Path):
    seg1 = _make_segment("片段一", SEGMENT_STATUS_DONE, segment_index=1)
    seg2 = _make_segment("片段二", SEGMENT_STATUS_FAILED, segment_index=2)
    seg2.error = "boom"
    config, manifest, manifest_path, chapter, segments_path = _setup_manifest_with_segments(
        tmp_path, [seg1, seg2]
    )
    chapter.segment_count = 2
    chapter.status = TTS_STATUS_FAILED
    chapter.error = "boom"
    wav1 = expected_segment_wav_path(config, chapter, seg1)
    write_test_wav(wav1, sample_rate=config.cosyvoice.sample_rate)
    seg1.wav_path = str(wav1)
    save_segments(segments_path, [seg1, seg2])
    manifest.save(manifest_path)

    provider = CountingProvider(sample_rate=config.cosyvoice.sample_rate)
    synthesize_chapter(1, config, load_manifest(manifest_path), manifest_path, provider)

    assert len(provider.calls) == 1
    assert provider.calls[0][0] == seg2.text
    manifest = load_manifest(manifest_path)
    assert manifest.chapters[0].status == TTS_STATUS_DONE


def test_resume_removes_manifest_and_segments_tmp(tmp_path: Path):
    segment = _make_segment(status=SEGMENT_STATUS_PENDING)
    config, manifest, manifest_path, chapter, segments_path = _setup_manifest_with_segments(
        tmp_path, [segment]
    )

    manifest_tmp = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
    manifest_tmp.write_text('{"stale": true}', encoding="utf-8")
    segments_tmp = segments_path.with_suffix(segments_path.suffix + ".tmp")
    segments_tmp.write_text('[{"stale": true}]', encoding="utf-8")

    recover_manifest_state(
        config=config,
        manifest=manifest,
        manifest_path=manifest_path,
        retry_failed=False,
        merge_when_complete=False,
    )

    assert not manifest_tmp.exists()
    assert not segments_tmp.exists()
    assert manifest_path.exists()
    assert segments_path.exists()


def test_synthesize_chapter_ignores_stale_segments_tmp(tmp_path: Path):
    segment = _make_segment(status=SEGMENT_STATUS_PENDING)
    config, manifest, manifest_path, chapter, segments_path = _setup_manifest_with_segments(
        tmp_path, [segment]
    )
    wav_path = expected_segment_wav_path(config, chapter, segment)
    write_test_wav(wav_path, sample_rate=config.cosyvoice.sample_rate)

    stale_segment = asdict(segment)
    stale_segment["status"] = SEGMENT_STATUS_FAILED
    stale_segment["error"] = "stale tmp content"
    segments_tmp = segments_path.with_suffix(segments_path.suffix + ".tmp")
    segments_tmp.write_text(json.dumps([stale_segment]), encoding="utf-8")

    provider = CountingProvider(sample_rate=config.cosyvoice.sample_rate)
    synthesize_chapter(1, config, manifest, manifest_path, provider)

    assert not segments_tmp.exists()
    segments = load_segments(segments_path)
    assert segments[0].status == SEGMENT_STATUS_DONE
    assert len(provider.calls) == 0
