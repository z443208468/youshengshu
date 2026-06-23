import re

from .exceptions import ConfigError


def normalize_newlines(text: str) -> str:
    """Normalize CRLF/CR to LF."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def split_paragraph_blocks(text: str) -> list[str]:
    normalized = normalize_newlines(text).strip()
    if not normalized:
        return []

    blocks = re.split(r"\n\s*\n+", normalized)
    return [block.strip() for block in blocks if block.strip()]


def build_paragraph_batches(
    text: str,
    paragraphs_per_batch: int,
) -> list[list[str]]:
    if paragraphs_per_batch < 1:
        raise ConfigError("paragraphs_per_batch 必须 >= 1。")

    paragraphs = split_paragraph_blocks(text)
    if not paragraphs:
        raise ConfigError("输入文本没有可翻译段落。")

    batches: list[list[str]] = []
    for i in range(0, len(paragraphs), paragraphs_per_batch):
        batches.append(paragraphs[i : i + paragraphs_per_batch])

    return batches
