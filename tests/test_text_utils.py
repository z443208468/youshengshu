import pytest

from youshengshu.config import ChunkingConfig
from youshengshu.exceptions import ConfigError
from youshengshu.text_utils import (
    normalize_newlines,
    estimate_tokens,
    split_text_for_translation,
    calculate_chunk_budget,
    estimate_with_config,
    describe_chunks,
    split_sentence_blocks,
    split_single_oversized_word_explicitly_enabled,
)


def make_small_config(**overrides):
    data = dict(
        context_tokens=256,
        reserved_prompt_tokens=40,
        reserved_output_tokens=40,
        safety_ratio=0.75,
        english_chars_per_token=4.0,
        cjk_chars_per_token=1.2,
        split_mode="paragraph_sentence_word",
        allow_word_split=False,
    )
    data.update(overrides)
    return ChunkingConfig(**data)


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
        reserved_output_tokens=2048,
        safety_ratio=0.65,
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
        context_tokens=512,
        reserved_prompt_tokens=100,
        reserved_output_tokens=100,
        safety_ratio=0.72,
        english_chars_per_token=4.0,
        cjk_chars_per_token=1.2,
        allow_word_split=False,
    )

    text = " ".join(["word" for _ in range(1000)])
    prompt = "X"

    chunks = split_text_for_translation(text, config, prompt)
    assert len(chunks) >= 1
    all_text = " ".join(chunks)
    assert len(all_text.split()) >= 900


def test_split_text_for_translation_not_empty():
    config = ChunkingConfig(
        context_tokens=8192,
        reserved_prompt_tokens=1800,
        reserved_output_tokens=2048,
        safety_ratio=0.65,
        english_chars_per_token=4.0,
        cjk_chars_per_token=1.2,
    )

    chunks = split_text_for_translation("Hello world.", config, "Translate:")
    assert len(chunks) > 0


def test_chunking_preserves_short_paragraphs():
    config = make_small_config(context_tokens=1024)
    text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    chunks = split_text_for_translation(text, config, "Translate:")
    joined = "\n\n".join(chunks)
    assert "First paragraph." in joined
    assert "Second paragraph." in joined
    assert "Third paragraph." in joined


def test_chunking_merges_short_paragraphs():
    config = make_small_config(context_tokens=1024)
    text = "\n\n".join([f"Paragraph {i}." for i in range(1, 6)])
    chunks = split_text_for_translation(text, config, "Translate:")
    assert len(chunks) == 1


def test_oversized_paragraph_splits_by_sentence_boundary():
    config = make_small_config(context_tokens=180, reserved_output_tokens=40, safety_ratio=0.7)
    sentence = "This is a sentence with enough words to count. "
    text = (sentence * 40).strip()
    chunks = split_text_for_translation(text, config, "Translate:")
    assert len(chunks) > 1
    assert all(chunk.endswith(".") for chunk in chunks[:-1])


def test_oversized_sentence_splits_by_words_without_losing_order():
    config = make_small_config(context_tokens=160, reserved_output_tokens=40, safety_ratio=0.7)
    words = [f"word{i}" for i in range(200)]
    text = " ".join(words)
    chunks = split_text_for_translation(text, config, "Translate:")
    recovered = " ".join(chunks).split()
    assert recovered == words


def test_single_oversized_word_raises_by_default():
    config = make_small_config(context_tokens=128, reserved_output_tokens=40, safety_ratio=0.7)
    text = "x" * 2000
    with pytest.raises(ConfigError):
        split_text_for_translation(text, config, "Translate:")


def test_single_oversized_word_can_split_only_when_enabled():
    config = make_small_config(
        context_tokens=128,
        reserved_output_tokens=40,
        safety_ratio=0.7,
        allow_word_split=True,
    )
    text = "x" * 2000
    chunks = split_text_for_translation(text, config, "Translate:")
    assert len(chunks) > 1
    assert "".join(chunks) == text


def test_chunks_do_not_exceed_available_source_budget():
    config = make_small_config(context_tokens=256, reserved_output_tokens=40, safety_ratio=0.7)
    prompt = "Translate:"
    text = "\n\n".join(["This is a paragraph. " * 20 for _ in range(20)])

    budget = calculate_chunk_budget(config, prompt)
    chunks = split_text_for_translation(text, config, prompt)

    assert chunks
    assert all(
        estimate_with_config(chunk, config) <= budget.available_source_tokens
        for chunk in chunks
    )


def test_split_sentence_blocks_handles_quote_after_punctuation():
    text = '"Hello." She turned away. "Goodbye." He left.'
    sentences = split_sentence_blocks(text)
    assert len(sentences) >= 2
    assert sentences[0].startswith('"Hello."')
    assert "She turned away." in sentences[1] or sentences[1].startswith("She")


def test_allow_word_split_cjk_parts_within_budget():
    config = make_small_config(
        context_tokens=128,
        reserved_output_tokens=40,
        safety_ratio=0.7,
        allow_word_split=True,
        cjk_chars_per_token=1.2,
    )
    budget = calculate_chunk_budget(config, "Translate:")
    word = "你" * 500
    parts = split_single_oversized_word_explicitly_enabled(word, config, budget)
    assert len(parts) > 1
    assert "".join(parts) == word
    assert all(
        estimate_with_config(p, config) <= budget.available_source_tokens
        for p in parts
    )


def test_describe_chunks_returns_debug_info():
    config = make_small_config(context_tokens=1024)
    chunks = ["Hello world.", "Second chunk."]
    infos = describe_chunks(chunks, config)
    assert len(infos) == 2
    assert infos[0].index == 1
    assert infos[0].chars == len(chunks[0])
