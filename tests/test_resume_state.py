import pytest

from youshengshu.exceptions import TranslationStateError
from youshengshu.resume_state import (
    TranslationBatchRecord,
    new_resume_state,
    append_translated_batch,
    save_resume_state_atomic,
    load_resume_state,
    validate_resume_state,
    render_partial_text,
    RESUME_STATE_VERSION,
)


def test_new_resume_state_initial_cursor_is_zero():
    state = new_resume_state(1, "sha", 5)
    assert state.completed_paragraph_count == 0
    assert state.completed_batch_count == 0
    assert state.batches == []


def test_append_batch_updates_cursor():
    state = new_resume_state(1, "sha", 3)
    paragraphs = ["p1", "p2", "p3"]

    append_translated_batch(state, paragraphs, 0, 1, "译文1")

    assert state.completed_paragraph_count == 1
    assert state.completed_batch_count == 1


def test_save_and_load_roundtrip(tmp_path):
    state = new_resume_state(1, "sha", 2)
    paragraphs = ["p1", "p2"]
    append_translated_batch(state, paragraphs, 0, 1, "译文1")

    path = tmp_path / "resume.json"
    save_resume_state_atomic(state, path)

    loaded = load_resume_state(path)
    assert loaded is not None
    assert loaded.version == RESUME_STATE_VERSION
    assert loaded.completed_paragraph_count == 1
    assert len(loaded.batches) == 1


def test_validate_resume_state_rejects_source_hash_mismatch():
    state = new_resume_state(1, "old_sha", 2)
    paragraphs = ["p1", "p2"]
    append_translated_batch(state, paragraphs, 0, 1, "译文1")

    with pytest.raises(TranslationStateError, match="hash"):
        validate_resume_state(state, 1, "new_sha", paragraphs)


def test_validate_resume_state_rejects_non_contiguous_batches():
    state = new_resume_state(1, "sha", 3)
    state.batches.append(
        TranslationBatchRecord(
            start=0,
            end=1,
            source_sha256="x",
            translated_text="t",
        )
    )
    state.completed_paragraph_count = 2
    state.completed_batch_count = 1

    paragraphs = ["p1", "p2", "p3"]

    with pytest.raises(TranslationStateError):
        validate_resume_state(state, 1, "sha", paragraphs)


def test_render_partial_text():
    state = new_resume_state(1, "sha", 2)
    paragraphs = ["p1", "p2"]
    append_translated_batch(state, paragraphs, 0, 1, "译文1")
    append_translated_batch(state, paragraphs, 1, 2, "译文2")

    assert render_partial_text(state) == "译文1\n\n译文2"
