import json
import os
from pathlib import Path

import pytest

from youshengshu_tts.cli import main
from youshengshu_tts.config import TtsAppConfig, TtsAudioConfig, TtsPathsConfig, TtsSegmentationConfig, CosyVoiceHttpConfig, save_tts_config
from youshengshu_tts.manifest import TTS_STATUS_DONE, TTS_STATUS_FAILED, load_manifest
from youshengshu_tts.pipeline import TtsPipelineStoppedError, create_project, synthesize_chapter
from youshengshu_tts.providers.fake import FakeTtsProvider


def _write_cn_chapters(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    long_para = "这是一段用于测试分段与合成的中文内容。" * 30
    (root / "chapter_001_cn.txt").write_text(
        long_para + "\n\n" + long_para,
        encoding="utf-8",
    )
    (root / "chapter_002_cn.txt").write_text("另一章内容。" * 30, encoding="utf-8")


def _make_config(tmp_path: Path) -> TtsAppConfig:
    cn_dir = tmp_path / "cn_chapters"
    _write_cn_chapters(cn_dir)
    output_dir = tmp_path / "audio_projects" / "default"
    return TtsAppConfig(
        paths=TtsPathsConfig(
            source_mode="cn_chapters_dir",
            source_path=str(cn_dir),
            output_dir=str(output_dir),
            manifest_file=str(output_dir / "audio_manifest.json"),
        ),
        segmentation=TtsSegmentationConfig(),
        cosyvoice=CosyVoiceHttpConfig(),
        audio=TtsAudioConfig(),
    )


def test_create_project_from_cn_chapters_dir(tmp_path: Path):
    config = _make_config(tmp_path)
    manifest = create_project(config)
    assert len(manifest.chapters) == 2
    assert manifest.chapters[0].index == 1


def test_synthesize_chapter_writes_segment_wav(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("YSS_TTS_FAKE_PROVIDER", "1")
    config = _make_config(tmp_path)
    manifest = create_project(config)
    manifest_path = Path(config.paths.manifest_file)
    provider = FakeTtsProvider()

    synthesize_chapter(1, config, manifest, manifest_path, provider)

    manifest = load_manifest(manifest_path)
    chapter = manifest.chapters[0]
    assert chapter.status == TTS_STATUS_DONE
    assert chapter.chapter_wav_path
    assert Path(chapter.chapter_wav_path).exists()


def test_failure_stops_at_failed_segment(tmp_path: Path):
    config = _make_config(tmp_path)
    manifest = create_project(config)
    manifest_path = Path(config.paths.manifest_file)

    class FailingProvider(FakeTtsProvider):
        def __init__(self):
            self.calls = 0

        def synthesize_to_file(self, text, output_path):
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("boom")
            return super().synthesize_to_file(text, output_path)

    provider = FailingProvider()
    with pytest.raises(TtsPipelineStoppedError):
        synthesize_chapter(1, config, manifest, manifest_path, provider)

    manifest = load_manifest(manifest_path)
    assert manifest.chapters[0].status == TTS_STATUS_FAILED


def test_rerun_skips_done_segment_and_continues(tmp_path: Path):
    config = _make_config(tmp_path)
    manifest = create_project(config)
    manifest_path = Path(config.paths.manifest_file)

    class FailingThenOkProvider(FakeTtsProvider):
        def __init__(self):
            self.calls = 0

        def synthesize_to_file(self, text, output_path):
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("boom")
            return super().synthesize_to_file(text, output_path)

    provider = FailingThenOkProvider()
    with pytest.raises(TtsPipelineStoppedError):
        synthesize_chapter(1, config, manifest, manifest_path, provider)

    synthesize_chapter(1, config, load_manifest(manifest_path), manifest_path, FakeTtsProvider())
    manifest = load_manifest(manifest_path)
    assert manifest.chapters[0].status == TTS_STATUS_DONE
    assert Path(manifest.chapters[0].chapter_wav_path).exists()


def test_cli_doctor_create_status_synthesize(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("YSS_TTS_FAKE_PROVIDER", "1")
    config = _make_config(tmp_path)
    config_path = tmp_path / "tts_config.json"
    save_tts_config(config, config_path)

    assert main(["--config", str(config_path), "doctor", "--json"]) == 0
    assert main(["--config", str(config_path), "create-project", "--json"]) == 0

    status_code = main(["--config", str(config_path), "status", "--json"])
    assert status_code == 0

    synth_code = main(["--config", str(config_path), "synthesize", "--chapter-index", "1", "--json"])
    assert synth_code == 0

    manifest = load_manifest(Path(config.paths.manifest_file))
    assert manifest.chapters[0].status == TTS_STATUS_DONE
