from youshengshu.text_utils import (
    normalize_newlines,
    estimate_tokens,
    split_text_for_translation,
)
from youshengshu.config import ChunkingConfig


def test_normalize_newlines():
    assert normalize_newlines("hello\r\nworld") == "hello\nworld"
    assert normalize_newlines("hello\rworld") == "hello\nworld"
    assert normalize_newlines("hello\nworld") == "hello\nworld"


def test_estimate_tokens_english():
    text = "The quick brown fox jumps over the lazy dog."
    tokens = estimate_tokens(text, english_chars_per_token=4.0, cjk_chars_per_token=1.2)
    assert tokens >= 1


def test_estimate_tokens_returns_at_least_one():
    assert estimate_tokens("", 4.0, 1.2) == 1
    assert estimate_tokens("a", 4.0, 1.2) == 1


def test_split_text_for_translation_preserves_paragraphs():
    config = ChunkingConfig(
        context_tokens=8192,
        reserved_prompt_tokens=1800,
        reserved_output_tokens=4096,
        safety_ratio=0.72,
        english_chars_per_token=4.0,
        cjk_chars_per_token=1.2,
    )

    text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    prompt = "System: translate this."

    chunks = split_text_for_translation(text, config, prompt)
    assert len(chunks) >= 1
    assert "First paragraph" in chunks[0]


def test_split_text_for_translation_large_paragraph():
    config = ChunkingConfig(
        context_tokens=512,  # Small context to force splitting
        reserved_prompt_tokens=100,
        reserved_output_tokens=100,
        safety_ratio=0.72,
        english_chars_per_token=4.0,
        cjk_chars_per_token=1.2,
    )

    # Create a long paragraph
    text = " ".join(["word" for _ in range(1000)])
    prompt = "X"

    chunks = split_text_for_translation(text, config, prompt)
    assert len(chunks) >= 1
    # Should preserve all words
    all_text = " ".join(chunks)
    assert len(all_text.split()) >= 900  # Most words preserved


def test_split_text_for_translation_not_empty():
    config = ChunkingConfig(
        context_tokens=8192,
        reserved_prompt_tokens=1800,
        reserved_output_tokens=4096,
        safety_ratio=0.72,
        english_chars_per_token=4.0,
        cjk_chars_per_token=1.2,
    )

    chunks = split_text_for_translation("Hello world.", config, "Translate:")
    assert len(chunks) > 0
