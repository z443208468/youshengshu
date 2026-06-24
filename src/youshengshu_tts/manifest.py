from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
from typing import Optional


TTS_STATUS_PENDING = "pending"
TTS_STATUS_SEGMENTED = "segmented"
TTS_STATUS_IN_PROGRESS = "in_progress"
TTS_STATUS_DONE = "done"
TTS_STATUS_FAILED = "failed"

SEGMENT_STATUS_PENDING = "pending"
SEGMENT_STATUS_DONE = "done"
SEGMENT_STATUS_FAILED = "failed"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class TtsSegment:
    chapter_index: int
    segment_index: int
    text: str
    text_sha256: str
    status: str = SEGMENT_STATUS_PENDING
    wav_path: Optional[str] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None


@dataclass
class TtsChapter:
    index: int
    title: str
    source_path: str
    source_sha256: str
    status: str = TTS_STATUS_PENDING
    segment_count: int = 0
    done_segment_count: int = 0
    failed_segment_count: int = 0
    segments_path: Optional[str] = None
    chapter_wav_path: Optional[str] = None
    chapter_mp3_path: Optional[str] = None
    error: Optional[str] = None


@dataclass
class TtsManifest:
    project_id: str
    source_mode: str
    source_path: str
    output_dir: str
    created_at: str
    updated_at: str
    chapters: list[TtsChapter]

    def save(self, path: Path) -> None:
        self.updated_at = now_iso()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)


def _chapter_from_dict(data: dict) -> TtsChapter:
    return TtsChapter(
        index=int(data["index"]),
        title=str(data["title"]),
        source_path=str(data["source_path"]),
        source_sha256=str(data["source_sha256"]),
        status=str(data.get("status", TTS_STATUS_PENDING)),
        segment_count=int(data.get("segment_count", 0)),
        done_segment_count=int(data.get("done_segment_count", 0)),
        failed_segment_count=int(data.get("failed_segment_count", 0)),
        segments_path=data.get("segments_path"),
        chapter_wav_path=data.get("chapter_wav_path"),
        chapter_mp3_path=data.get("chapter_mp3_path"),
        error=data.get("error"),
    )


def load_manifest(path: Path) -> TtsManifest:
    if not path.exists():
        raise FileNotFoundError(f"TTS manifest 不存在: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    chapters = [_chapter_from_dict(item) for item in data.get("chapters", [])]

    return TtsManifest(
        project_id=str(data["project_id"]),
        source_mode=str(data["source_mode"]),
        source_path=str(data["source_path"]),
        output_dir=str(data["output_dir"]),
        created_at=str(data["created_at"]),
        updated_at=str(data["updated_at"]),
        chapters=chapters,
    )


def chapter_summary(chapter: TtsChapter) -> dict:
    return {
        "index": chapter.index,
        "title": chapter.title,
        "source_path": chapter.source_path,
        "status": chapter.status,
        "segment_count": chapter.segment_count,
        "done_segment_count": chapter.done_segment_count,
        "failed_segment_count": chapter.failed_segment_count,
        "chapter_wav_path": chapter.chapter_wav_path,
        "chapter_mp3_path": chapter.chapter_mp3_path,
        "error": chapter.error,
    }


def manifest_status_payload(manifest: TtsManifest) -> dict:
    total = len(manifest.chapters)
    done = sum(1 for chapter in manifest.chapters if chapter.status == TTS_STATUS_DONE)
    failed = sum(1 for chapter in manifest.chapters if chapter.status == TTS_STATUS_FAILED)
    in_progress = sum(1 for chapter in manifest.chapters if chapter.status == TTS_STATUS_IN_PROGRESS)
    pending = total - done - failed - in_progress

    return {
        "project_id": manifest.project_id,
        "source_mode": manifest.source_mode,
        "source_path": manifest.source_path,
        "output_dir": manifest.output_dir,
        "total": total,
        "done": done,
        "pending": pending,
        "failed": failed,
        "in_progress": in_progress,
        "chapters": [chapter_summary(chapter) for chapter in manifest.chapters],
    }
