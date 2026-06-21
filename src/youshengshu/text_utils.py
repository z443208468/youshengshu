import math
import re

from .config import ChunkingConfig
from .exceptions import ConfigError

SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?。！？])\s+")


def normalize_newlines(text: str) -> str:
    """Normalize \\r\\n and \\r to \\n."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def estimate_tokens(
    text: str,
    english_chars_per_token: float = 4.0,
    cjk_chars_per_token: float = 1.2,
) -> int:
    """Roughly estimate token count without a real tokenizer."""
    ascii_like_chars = sum(1 for ch in text if ord(ch) < 128 and not ch.isspace())
    total_non_whitespace = sum(1 for ch in text if not ch.isspace())
    cjk_like_chars = total_non_whitespace - ascii_like_chars

    estimated = math.ceil(
        ascii_like_chars / english_chars_per_token
        + cjk_like_chars / cjk_chars_per_token
    )
    return max(1, estimated)


def split_text_for_translation(
    text: str,
    config: ChunkingConfig,
    prompt_text: str,
) -> list[str]:
    """Split source text into chunks that fit within the model's context budget."""

    prompt_tokens = estimate_tokens(
        prompt_text,
        config.english_chars_per_token,
        config.cjk_chars_per_token,
    )

    available_source_tokens = math.floor(
        (config.context_tokens - prompt_tokens - config.reserved_output_tokens)
        * config.safety_ratio
    )

    if available_source_tokens <= 0:
        raise ConfigError(
            f"可用 source token 预算为 {available_source_tokens}，"
            f"请检查 context_tokens({config.context_tokens})、"
            f"reserved_output_tokens({config.reserved_output_tokens}) 和提示词长度。"
        )

    paragraphs = re.split(r"\n\n+\s*", text.strip())
    chunks: list[str] = []
    current_chunk = ""

    for para in paragraphs:
        para_stripped = para.strip()
        if not para_stripped:
            continue

        candidate = (current_chunk + "\n\n" + para_stripped) if current_chunk else para_stripped

        if estimate_tokens(candidate, config.english_chars_per_token, config.cjk_chars_per_token) <= available_source_tokens:
            current_chunk = candidate
        else:
            if current_chunk:
                chunks.append(current_chunk)

            para_tokens = estimate_tokens(para_stripped, config.english_chars_per_token, config.cjk_chars_per_token)
            if para_tokens <= available_source_tokens:
                current_chunk = para_stripped
            else:
                split_paragraphs = _split_oversized_paragraph(
                    para_stripped,
                    available_source_tokens,
                    config.english_chars_per_token,
                    config.cjk_chars_per_token,
                )
                for sp in split_paragraphs:
                    if current_chunk:
                        chunks.append(current_chunk)
                    current_chunk = sp

    if current_chunk:
        chunks.append(current_chunk)

    if not chunks:
        raise ConfigError("切分后 chunk 列表为空，请检查输入文本。")

    return chunks


def _split_oversized_paragraph(
    paragraph: str,
    available_source_tokens: int,
    english_chars_per_token: float,
    cjk_chars_per_token: float,
) -> list[str]:
    """Split an oversized paragraph by sentence boundaries, then by spaces, then by char window."""

    sentences = SENTENCE_BOUNDARY_RE.split(paragraph)
    result: list[str] = []
    current = ""

    for sentence in sentences:
        candidate = (current + " " + sentence) if current else sentence
        if estimate_tokens(candidate, english_chars_per_token, cjk_chars_per_token) <= available_source_tokens:
            current = candidate
        else:
            if current:
                result.append(current)
            # Check if single sentence still exceeds
            sent_tokens = estimate_tokens(sentence, english_chars_per_token, cjk_chars_per_token)
            if sent_tokens <= available_source_tokens:
                current = sentence
            else:
                # Split by space
                words = sentence.split()
                sub_current = ""
                for word in words:
                    sub_candidate = (sub_current + " " + word) if sub_current else word
                    if estimate_tokens(sub_candidate, english_chars_per_token, cjk_chars_per_token) <= available_source_tokens:
                        sub_current = sub_candidate
                    else:
                        if sub_current:
                            result.append(sub_current)
                        # If single word exceeds limit, split by char window
                        word_tokens = estimate_tokens(word, english_chars_per_token, cjk_chars_per_token)
                        if word_tokens <= available_source_tokens:
                            sub_current = word
                        else:
                            char_limit = int(available_source_tokens * english_chars_per_token)
                            for i in range(0, len(word), char_limit):
                                result.append(word[i : i + char_limit])
                            sub_current = ""
                if sub_current:
                    current = sub_current
                else:
                    current = ""

    if current:
        result.append(current)

    return result
