import pytest

from youshengshu_tts.cli import main


def test_cli_doctor_json(tmp_path, monkeypatch: pytest.MonkeyPatch):
    from youshengshu_tts.config import (
        CosyVoiceHttpConfig,
        TtsAppConfig,
        TtsAudioConfig,
        TtsPathsConfig,
        TtsSegmentationConfig,
        save_tts_config,
    )

    config = TtsAppConfig(
        paths=TtsPathsConfig(
            source_mode="cn_chapters_dir",
            source_path=str(tmp_path / "cn"),
            output_dir=str(tmp_path / "out"),
            manifest_file=str(tmp_path / "out" / "audio_manifest.json"),
        ),
        segmentation=TtsSegmentationConfig(),
        cosyvoice=CosyVoiceHttpConfig(),
        audio=TtsAudioConfig(),
    )
    (tmp_path / "cn").mkdir()
    config_path = tmp_path / "tts_config.json"
    save_tts_config(config, config_path)

    assert main(["--config", str(config_path), "doctor", "--json"]) == 0


def test_cli_create_project_and_status(tmp_path, monkeypatch: pytest.MonkeyPatch):
    from youshengshu_tts.config import (
        CosyVoiceHttpConfig,
        TtsAppConfig,
        TtsAudioConfig,
        TtsPathsConfig,
        TtsSegmentationConfig,
        save_tts_config,
    )

    cn_dir = tmp_path / "cn_chapters"
    cn_dir.mkdir()
    (cn_dir / "chapter_001_cn.txt").write_text("测试章节内容。" * 20, encoding="utf-8")

    output_dir = tmp_path / "audio_projects" / "default"
    config = TtsAppConfig(
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
    config_path = tmp_path / "tts_config.json"
    save_tts_config(config, config_path)

    assert main(["--config", str(config_path), "create-project", "--json"]) == 0
    assert main(["--config", str(config_path), "status", "--json"]) == 0


def test_cli_synthesize_chapter_with_fake_provider(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("YSS_TTS_FAKE_PROVIDER", "1")

    from youshengshu_tts.config import (
        CosyVoiceHttpConfig,
        TtsAppConfig,
        TtsAudioConfig,
        TtsPathsConfig,
        TtsSegmentationConfig,
        save_tts_config,
    )

    cn_dir = tmp_path / "cn_chapters"
    cn_dir.mkdir()
    (cn_dir / "chapter_001_cn.txt").write_text("测试章节内容。" * 20, encoding="utf-8")

    output_dir = tmp_path / "audio_projects" / "default"
    config = TtsAppConfig(
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
    config_path = tmp_path / "tts_config.json"
    save_tts_config(config, config_path)

    main(["--config", str(config_path), "create-project", "--json"])
    assert main(["--config", str(config_path), "synthesize", "--chapter-index", "1", "--json"]) == 0
