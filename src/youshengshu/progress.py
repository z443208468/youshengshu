import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .chapter_splitter import ChapterFileRecord


TRANSLATION_STATUS_PENDING = "pending"
TRANSLATION_STATUS_IN_PROGRESS = "in_progress"
TRANSLATION_STATUS_DONE = "done"
TRANSLATION_STATUS_FAILED = "failed"

VALID_STATUSES = {
    TRANSLATION_STATUS_PENDING,
    TRANSLATION_STATUS_IN_PROGRESS,
    TRANSLATION_STATUS_DONE,
    TRANSLATION_STATUS_FAILED,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def expected_cn_path_for_en_path(en_path: str, cn_chapters_dir: str) -> str:
    en_name = Path(en_path).name

    if en_name.endswith("_en.txt"):
        cn_name = en_name.replace("_en.txt", "_cn.txt")
    else:
        stem = Path(en_name).stem
        cn_name = f"{stem}_cn.txt"

    return str(Path(cn_chapters_dir) / cn_name)


def expected_partial_path_for_cn_path(cn_path: str) -> str:
    path = Path(cn_path)
    if path.name.endswith("_cn.txt"):
        return str(path.with_name(path.name.replace("_cn.txt", "_cn.partial.txt")))
    return str(path.with_suffix(path.suffix + ".partial"))


def expected_resume_state_path_for_cn_path(cn_path: str) -> str:
    path = Path(cn_path)
    if path.name.endswith("_cn.txt"):
        return str(path.with_name(path.name.replace("_cn.txt", "_cn.resume.json")))
    return str(path.with_suffix(path.suffix + ".resume.json"))


def _legacy_cn_path_same_dir(en_path: str) -> str:
    """Fallback when manifest has no cn_path (legacy). Prefer expected_cn_path_for_en_path."""
    suffix_en = "_en.txt"
    suffix_cn = "_cn.txt"
    if en_path.endswith(suffix_en):
        return en_path[: -len(suffix_en)] + suffix_cn
    return f"{en_path}{suffix_cn}" if not en_path.endswith(suffix_cn) else en_path


class ManifestChapter:
    def __init__(
        self,
        index: int,
        title: str,
        en_path: str,
        source_sha256: str,
        cn_path: Optional[str] = None,
        translation_status: str = TRANSLATION_STATUS_PENDING,
        translated_at: Optional[str] = None,
        translation_model: Optional[str] = None,
        chunk_count: Optional[int] = None,
        error: Optional[str] = None,
        translated_paragraph_count: int = 0,
        source_paragraph_count: int = 0,
        translated_batch_count: int = 0,
        partial_path: Optional[str] = None,
        resume_state_path: Optional[str] = None,
    ):
        self.index = index
        self.title = title
        self.en_path = en_path
        self.cn_path = cn_path if cn_path else _legacy_cn_path_same_dir(en_path)
        self.source_sha256 = source_sha256
        self.translation_status = translation_status
        self.translated_at = translated_at
        self.translation_model = translation_model
        self.chunk_count = chunk_count
        self.error = error
        self.translated_paragraph_count = translated_paragraph_count
        self.source_paragraph_count = source_paragraph_count
        self.translated_batch_count = translated_batch_count
        self.partial_path = partial_path
        self.resume_state_path = resume_state_path

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "title": self.title,
            "en_path": self.en_path,
            "cn_path": self.cn_path,
            "source_sha256": self.source_sha256,
            "translation_status": self.translation_status,
            "translated_at": self.translated_at,
            "translation_model": self.translation_model,
            "chunk_count": self.chunk_count,
            "error": self.error,
            "translated_paragraph_count": self.translated_paragraph_count,
            "source_paragraph_count": self.source_paragraph_count,
            "translated_batch_count": self.translated_batch_count,
            "partial_path": self.partial_path,
            "resume_state_path": self.resume_state_path,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ManifestChapter":
        return cls(
            index=data["index"],
            title=data["title"],
            en_path=data["en_path"],
            cn_path=data.get("cn_path", ""),
            source_sha256=data["source_sha256"],
            translation_status=data.get("translation_status", TRANSLATION_STATUS_PENDING),
            translated_at=data.get("translated_at"),
            translation_model=data.get("translation_model"),
            chunk_count=data.get("chunk_count"),
            error=data.get("error"),
            translated_paragraph_count=int(data.get("translated_paragraph_count") or 0),
            source_paragraph_count=int(data.get("source_paragraph_count") or 0),
            translated_batch_count=int(data.get("translated_batch_count") or 0),
            partial_path=data.get("partial_path"),
            resume_state_path=data.get("resume_state_path"),
        )


class TranslationManifest:
    def __init__(
        self,
        source_file: str = "",
        chapters: Optional[list[ManifestChapter]] = None,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
    ):
        self.source_file = source_file
        self.chapters = chapters or []
        self.created_at = created_at or _now_iso()
        self.updated_at = updated_at or _now_iso()

    def to_dict(self) -> dict:
        return {
            "source_file": self.source_file,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "chapter_count": len(self.chapters),
            "chapters": [ch.to_dict() for ch in self.chapters],
        }

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.updated_at = _now_iso()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: Path) -> "TranslationManifest":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        chapters = [ManifestChapter.from_dict(ch) for ch in data.get("chapters", [])]
        return cls(
            source_file=data.get("source_file", ""),
            chapters=chapters,
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    @classmethod
    def create_from_records(
        cls,
        source_file: str,
        records: list[ChapterFileRecord],
        cn_chapters_dir: str,
    ) -> "TranslationManifest":
        now = _now_iso()
        chapters = [
            ManifestChapter(
                index=r.index,
                title=r.title,
                en_path=r.filepath,
                cn_path=expected_cn_path_for_en_path(r.filepath, cn_chapters_dir),
                source_sha256=r.sha256,
                translation_status=TRANSLATION_STATUS_PENDING,
            )
            for r in records
        ]
        return cls(
            source_file=source_file,
            chapters=chapters,
            created_at=now,
            updated_at=now,
        )

    def normalize_cn_paths(self, cn_chapters_dir: str, move_existing: bool = True) -> list[int]:
        changed: list[int] = []

        for ch in self.chapters:
            expected = expected_cn_path_for_en_path(ch.en_path, cn_chapters_dir)
            old = ch.cn_path

            if old == expected:
                continue

            old_path = Path(old)
            new_path = Path(expected)
            new_path.parent.mkdir(parents=True, exist_ok=True)

            if move_existing and old_path.exists() and not new_path.exists():
                old_path.replace(new_path)

            old_partial = Path(expected_partial_path_for_cn_path(old))
            new_partial = Path(expected_partial_path_for_cn_path(expected))
            if move_existing and old_partial.exists() and not new_partial.exists():
                new_partial.parent.mkdir(parents=True, exist_ok=True)
                old_partial.replace(new_partial)

            old_resume = Path(expected_resume_state_path_for_cn_path(old))
            new_resume = Path(expected_resume_state_path_for_cn_path(expected))
            if move_existing and old_resume.exists() and not new_resume.exists():
                new_resume.parent.mkdir(parents=True, exist_ok=True)
                old_resume.replace(new_resume)

            ch.cn_path = expected
            ch.partial_path = str(new_partial) if new_partial.exists() else None
            ch.resume_state_path = str(new_resume) if new_resume.exists() else None
            changed.append(ch.index)

        return changed

    def get_chapter_by_index(self, index: int) -> Optional[ManifestChapter]:
        for ch in self.chapters:
            if ch.index == index:
                return ch
        return None

    def set_chapter_status(
        self,
        index: int,
        status: str,
        error: Optional[str] = None,
        model: Optional[str] = None,
        chunk_count: Optional[int] = None,
    ) -> None:
        if status not in VALID_STATUSES:
            raise ValueError(f"无效状态: {status}")
        ch = self.get_chapter_by_index(index)
        if ch:
            ch.translation_status = status

            if status == TRANSLATION_STATUS_DONE:
                ch.error = None
                ch.translated_at = _now_iso()
            elif error is not None:
                ch.error = error

            if model is not None:
                ch.translation_model = model
            if chunk_count is not None:
                ch.chunk_count = chunk_count

    def get_next_pending_chapter(self) -> Optional[ManifestChapter]:
        for ch in self.chapters:
            if ch.translation_status in (
                TRANSLATION_STATUS_PENDING,
                TRANSLATION_STATUS_FAILED,
            ):
                return ch
            if ch.translation_status == TRANSLATION_STATUS_IN_PROGRESS:
                cn_path = Path(ch.cn_path)
                if not cn_path.exists():
                    return ch
        return None

    def get_summary(self) -> dict:
        counts = {"total": len(self.chapters), "done": 0, "pending": 0, "failed": 0, "in_progress": 0}
        failed_list = []
        for ch in self.chapters:
            if ch.translation_status == TRANSLATION_STATUS_DONE:
                counts["done"] += 1
            elif ch.translation_status == TRANSLATION_STATUS_FAILED:
                counts["failed"] += 1
                failed_list.append((ch.index, ch.en_path, ch.error or "未知错误"))
            elif ch.translation_status == TRANSLATION_STATUS_IN_PROGRESS:
                counts["in_progress"] += 1
            else:
                counts["pending"] += 1

        next_ch = self.get_next_pending_chapter()
        counts["next_chapter"] = next_ch.index if next_ch else None
        counts["failed_list"] = failed_list
        return counts

    def check_and_reset_stale(self) -> list[int]:
        """Reset chapters whose source sha256 doesn't match the actual file.
        Returns list of reset chapter indices."""
        reset_indices = []
        for ch in self.chapters:
            en_path = Path(ch.en_path)
            if en_path.exists():
                actual_sha256 = _file_sha256(en_path)
                if actual_sha256 != ch.source_sha256:
                    ch.source_sha256 = actual_sha256
                    ch.translation_status = TRANSLATION_STATUS_PENDING
                    ch.error = None
                    ch.translated_at = None
                    ch.translation_model = None
                    ch.chunk_count = None
                    if ch.partial_path:
                        Path(ch.partial_path).unlink(missing_ok=True)
                    if ch.resume_state_path:
                        Path(ch.resume_state_path).unlink(missing_ok=True)
                    ch.translated_paragraph_count = 0
                    ch.source_paragraph_count = 0
                    ch.translated_batch_count = 0
                    ch.partial_path = None
                    ch.resume_state_path = None
                    reset_indices.append(ch.index)
        return reset_indices


def _file_sha256(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
