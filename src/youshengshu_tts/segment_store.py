import json
from dataclasses import asdict
from pathlib import Path

from .manifest import (
    SEGMENT_STATUS_PENDING,
    TtsSegment,
)


def load_segments(path: Path) -> list[TtsSegment]:
    if not path.exists():
        raise FileNotFoundError(f"TTS segments 文件不存在: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    segments: list[TtsSegment] = []

    for item in data:
        segments.append(
            TtsSegment(
                chapter_index=int(item["chapter_index"]),
                segment_index=int(item["segment_index"]),
                text=str(item["text"]),
                text_sha256=str(item["text_sha256"]),
                status=str(item.get("status", SEGMENT_STATUS_PENDING)),
                wav_path=item.get("wav_path"),
                duration_ms=item.get("duration_ms"),
                error=item.get("error"),
            )
        )

    return segments


def save_segments(path: Path, segments: list[TtsSegment]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps([asdict(segment) for segment in segments], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp.replace(path)
