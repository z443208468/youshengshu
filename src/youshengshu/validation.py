import warnings

from .exceptions import TranslationValidationError

KNOWN_PREAMBLES = [
    "以下是翻译：",
    "以下为中文译文：",
    "中文译文：",
    "译文：",
    "好的，以下是翻译：",
    "以下是中文翻译：",
    "以下是对应片段的中文翻译：",
    "翻译如下：",
    "以下是译文：",
]


def strip_known_preambles(text: str) -> str:
    """Remove common preambles that some models add before translations."""
    stripped = text.lstrip()
    for preamble in KNOWN_PREAMBLES:
        if stripped.startswith(preamble):
            stripped = stripped[len(preamble) :].lstrip()
            break
    return stripped


def validate_translation_chunk(source: str, translated: str) -> None:
    """Validate a translated chunk. Raise TranslationValidationError only for structurally unusable output."""

    stripped = translated.strip()
    if not stripped:
        raise TranslationValidationError("译文为空。")

    # Check first 200 chars for low Chinese ratio.
    # This remains a warning only; it must not fail the chapter.
    head = stripped[:200]
    if head:
        non_space_chars = [c for c in head if not c.isspace()]
        if non_space_chars:
            cjk_count = sum(1 for c in non_space_chars if ord(c) > 0x2E80)
            cjk_ratio = cjk_count / len(non_space_chars)
            if cjk_ratio < 0.1 and len(non_space_chars) > 50:
                warnings.warn(
                    "译文前200字符中中文字符比例极低，可能仍是英文原文。"
                )


def validate_translation_result(translated: str) -> str:
    """Strip preamble, validate, return cleaned result."""
    cleaned = strip_known_preambles(translated)
    validate_translation_chunk("", cleaned)
    return cleaned
