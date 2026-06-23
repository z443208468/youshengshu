import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from .exceptions import TranslationStateError

RESUME_STATE_VERSION = 1


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class TranslationBatchRecord:
    start: int
    end: int
    source_sha256: str
    translated_text: str


@dataclass
class TranslationResumeState:
    version: int
    chapter_index: int
    chapter_source_sha256: str
    total_paragraphs: int
    completed_paragraph_count: int
    completed_batch_count: int
    batches: list[TranslationBatchRecord]


def new_resume_state(
    chapter_index: int,
    chapter_source_sha256: str,
    total_paragraphs: int,
) -> TranslationResumeState:
    return TranslationResumeState(
        version=RESUME_STATE_VERSION,
        chapter_index=chapter_index,
        chapter_source_sha256=chapter_source_sha256,
        total_paragraphs=total_paragraphs,
        completed_paragraph_count=0,
        completed_batch_count=0,
        batches=[],
    )


def load_resume_state(path: str | Path) -> Optional[TranslationResumeState]:
    path = Path(path)
    if not path.exists():
        return None

    data = json.loads(path.read_text(encoding="utf-8"))

    batches = [
        TranslationBatchRecord(
            start=int(item["start"]),
            end=int(item["end"]),
            source_sha256=str(item["source_sha256"]),
            translated_text=str(item["translated_text"]),
        )
        for item in data.get("batches", [])
    ]

    return TranslationResumeState(
        version=int(data["version"]),
        chapter_index=int(data["chapter_index"]),
        chapter_source_sha256=str(data["chapter_source_sha256"]),
        total_paragraphs=int(data["total_paragraphs"]),
        completed_paragraph_count=int(data["completed_paragraph_count"]),
        completed_batch_count=int(data["completed_batch_count"]),
        batches=batches,
    )


def save_resume_state_atomic(state: TranslationResumeState, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = asdict(state)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp_path.replace(path)


def render_partial_text(state: TranslationResumeState) -> str:
    return "\n\n".join(batch.translated_text for batch in state.batches)


def validate_resume_state(
    state: TranslationResumeState,
    chapter_index: int,
    chapter_source_sha256: str,
    paragraphs: list[str],
) -> None:
    if state.version != RESUME_STATE_VERSION:
        raise TranslationStateError(
            f"不支持的 resume state version: {state.version}"
        )

    if state.chapter_index != chapter_index:
        raise TranslationStateError(
            f"resume chapter_index 不一致: state={state.chapter_index}, current={chapter_index}"
        )

    if state.chapter_source_sha256 != chapter_source_sha256:
        raise TranslationStateError("章节源文件 hash 已变化，不能复用旧断点。")

    if state.total_paragraphs != len(paragraphs):
        raise TranslationStateError(
            f"段落总数不一致: state={state.total_paragraphs}, current={len(paragraphs)}"
        )

    expected_cursor = 0
    for idx, batch in enumerate(state.batches):
        if batch.start != expected_cursor:
            raise TranslationStateError(
                f"resume batch 不连续: batch={idx}, start={batch.start}, expected={expected_cursor}"
            )

        if batch.end <= batch.start:
            raise TranslationStateError(
                f"resume batch 范围非法: batch={idx}, start={batch.start}, end={batch.end}"
            )

        if batch.end > len(paragraphs):
            raise TranslationStateError(
                f"resume batch 超出段落范围: batch={idx}, end={batch.end}, total={len(paragraphs)}"
            )

        source_text = "\n\n".join(paragraphs[batch.start : batch.end])
        if sha256_text(source_text) != batch.source_sha256:
            raise TranslationStateError(
                f"resume batch source hash 不一致: batch={idx}"
            )

        expected_cursor = batch.end

    if state.completed_paragraph_count != expected_cursor:
        raise TranslationStateError(
            f"completed_paragraph_count 不一致: state={state.completed_paragraph_count}, expected={expected_cursor}"
        )

    if state.completed_batch_count != len(state.batches):
        raise TranslationStateError(
            f"completed_batch_count 不一致: state={state.completed_batch_count}, expected={len(state.batches)}"
        )


def append_translated_batch(
    state: TranslationResumeState,
    paragraphs: list[str],
    start: int,
    end: int,
    translated_text: str,
) -> None:
    if start != state.completed_paragraph_count:
        raise TranslationStateError(
            f"不能追加非连续 batch: start={start}, expected={state.completed_paragraph_count}"
        )

    if end <= start:
        raise TranslationStateError(
            f"batch 范围非法: start={start}, end={end}"
        )

    source_text = "\n\n".join(paragraphs[start:end])

    state.batches.append(
        TranslationBatchRecord(
            start=start,
            end=end,
            source_sha256=sha256_text(source_text),
            translated_text=translated_text,
        )
    )
    state.completed_paragraph_count = end
    state.completed_batch_count = len(state.batches)
