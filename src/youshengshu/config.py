import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .exceptions import ConfigError


@dataclass
class PathsConfig:
    input_file: str = "data/input/ReZero_Watching_Him_Die.txt"
    en_chapters_dir: str = "data/en_chapters"
    cn_chapters_dir: str = "data/cn_chapters"
    manifest_file: str = "data/manifests/translation_manifest.json"


@dataclass
class ChapterSplitConfig:
    strict_chapter_sequence: bool = True
    min_valid_chapter_chars: int = 3000


@dataclass
class LMStudioConfig:
    base_url: str = "http://localhost:1234/v1"
    api_key: str = "lm-studio"
    model_id: str = "auto"
    temperature: float = 0.2
    top_p: float = 0.85
    max_output_tokens: int = 4096
    request_timeout_seconds: int = 600
    max_retries: int = 3
    retry_sleep_seconds: int = 5


@dataclass
class ChunkingConfig:
    context_tokens: int = 8192
    reserved_prompt_tokens: int = 1800
    reserved_output_tokens: int = 4096
    safety_ratio: float = 0.72
    english_chars_per_token: float = 4.0
    cjk_chars_per_token: float = 1.2


@dataclass
class TranslationConfig:
    skip_existing_done_chapters: bool = True
    write_partial_file: bool = True
    strip_model_preamble: bool = True


@dataclass
class AppConfig:
    paths: PathsConfig = field(default_factory=PathsConfig)
    chapter_split: ChapterSplitConfig = field(default_factory=ChapterSplitConfig)
    lmstudio: LMStudioConfig = field(default_factory=LMStudioConfig)
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    translation: TranslationConfig = field(default_factory=TranslationConfig)


def load_config(config_path: str) -> AppConfig:
    path = Path(config_path)
    if not path.exists():
        raise ConfigError(f"配置文件不存在: {config_path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    paths_data = data.get("paths", {})
    chapter_split_data = data.get("chapter_split", {})
    lmstudio_data = data.get("lmstudio", {})
    chunking_data = data.get("chunking", {})
    translation_data = data.get("translation", {})

    return AppConfig(
        paths=PathsConfig(**paths_data),
        chapter_split=ChapterSplitConfig(**chapter_split_data),
        lmstudio=LMStudioConfig(**lmstudio_data),
        chunking=ChunkingConfig(**chunking_data),
        translation=TranslationConfig(**translation_data),
    )
