from dataclasses import dataclass
import json
from pathlib import Path


@dataclass
class TtsPathsConfig:
    source_mode: str = "cn_chapters_dir"
    source_path: str = "data/cn_chapters"
    output_dir: str = "data/audio_projects/default"
    manifest_file: str = "data/audio_projects/default/audio_manifest.json"


@dataclass
class TtsSegmentationConfig:
    target_chars_min: int = 80
    target_chars_max: int = 180
    hard_chars_max: int = 240
    punctuation: str = "。！？；……\n"


@dataclass
class CosyVoiceHttpConfig:
    base_url: str = "http://127.0.0.1:50000"
    mode: str = "sft"
    spk_id: str = "中文女"
    prompt_text: str = ""
    prompt_audio_path: str = ""
    instruct_text: str = ""
    model_profile: str = "cosyvoice_300m_sft"
    request_timeout_seconds: int = 120
    max_retries: int = 2
    retry_sleep_seconds: int = 2
    sample_rate: int = 22050


@dataclass
class TtsAudioConfig:
    output_format: str = "wav"
    sample_rate: int = 22050


@dataclass
class TtsAppConfig:
    paths: TtsPathsConfig
    segmentation: TtsSegmentationConfig
    cosyvoice: CosyVoiceHttpConfig
    audio: TtsAudioConfig


def load_tts_config(path: str | Path) -> TtsAppConfig:
    path = Path(path)
    if not path.exists():
        config = TtsAppConfig(
            paths=TtsPathsConfig(),
            segmentation=TtsSegmentationConfig(),
            cosyvoice=CosyVoiceHttpConfig(),
            audio=TtsAudioConfig(),
        )
        validate_tts_config(config)
        return config

    data = json.loads(path.read_text(encoding="utf-8"))
    config = TtsAppConfig(
        paths=TtsPathsConfig(**data.get("paths", {})),
        segmentation=TtsSegmentationConfig(**data.get("segmentation", {})),
        cosyvoice=CosyVoiceHttpConfig(**data.get("cosyvoice", {})),
        audio=TtsAudioConfig(**data.get("audio", {})),
    )
    validate_tts_config(config)
    return config


def validate_tts_config(config: TtsAppConfig) -> None:
    if config.paths.source_mode not in {"txt_file", "cn_chapters_dir"}:
        raise ValueError(
            f"不支持的 source_mode: {config.paths.source_mode}; "
            "supported=['txt_file', 'cn_chapters_dir']"
        )

    if config.cosyvoice.mode not in {"sft", "zero_shot", "cross_lingual", "instruct"}:
        raise ValueError(
            f"不支持的 CosyVoice mode: {config.cosyvoice.mode}; "
            "supported=['sft', 'zero_shot', 'cross_lingual', 'instruct']"
        )


def save_tts_config(config: TtsAppConfig, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "paths": config.paths.__dict__,
        "segmentation": config.segmentation.__dict__,
        "cosyvoice": config.cosyvoice.__dict__,
        "audio": config.audio.__dict__,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
