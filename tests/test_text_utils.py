import pytest

from youshengshu.exceptions import ConfigError
from youshengshu.text_utils import (
    normalize_newlines,
    split_paragraph_blocks,
    build_paragraph_batches,
)


def test_normalize_newlines():
    assert normalize_newlines("a\r\nb\rc") == "a\nb\nc"


def test_split_paragraph_blocks_splits_on_blank_lines():
    text = "Para one.\n\nPara two.\n\nPara three."
    assert split_paragraph_blocks(text) == ["Para one.", "Para two.", "Para three."]


def test_build_paragraph_batches_uses_paragraph_as_minimum_unit():
    text = "Para one sentence one. Sentence two.\n\nPara two sentence one. Sentence two."
    batches = build_paragraph_batches(text, paragraphs_per_batch=1)

    assert batches == [
        ["Para one sentence one. Sentence two."],
        ["Para two sentence one. Sentence two."],
    ]


def test_build_paragraph_batches_groups_paragraphs_without_splitting():
    text = "A. B. C. D.\n\nE. F. G. H.\n\nI. J."
    batches = build_paragraph_batches(text, paragraphs_per_batch=2)

    assert batches == [
        ["A. B. C. D.", "E. F. G. H."],
        ["I. J."],
    ]


def test_single_long_paragraph_is_not_split():
    text = "word " * 10000
    batches = build_paragraph_batches(text, paragraphs_per_batch=1)

    assert len(batches) == 1
    assert len(batches[0]) == 1
    assert batches[0][0] == text.strip()


def test_build_paragraph_batches_rejects_invalid_batch_size():
    with pytest.raises(ConfigError):
        build_paragraph_batches("Para.", paragraphs_per_batch=0)


def test_build_paragraph_batches_rejects_empty_text():
    with pytest.raises(ConfigError):
        build_paragraph_batches("   ", paragraphs_per_batch=1)
