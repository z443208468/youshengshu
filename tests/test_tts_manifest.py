from pathlib import Path

from youshengshu_tts.manifest import (
    TTS_STATUS_PENDING,
    TtsChapter,
    TtsManifest,
    chapter_summary,
    load_manifest,
    manifest_status_payload,
    now_iso,
    sha256_text,
)


def test_manifest_save_and_load(tmp_path: Path):
    manifest = TtsManifest(
        project_id="test",
        source_mode="cn_chapters_dir",
        source_path="data/cn_chapters",
        output_dir=str(tmp_path),
        created_at=now_iso(),
        updated_at=now_iso(),
        chapters=[
            TtsChapter(
                index=1,
                title="chapter_001_cn",
                source_path="data/cn_chapters/chapter_001_cn.txt",
                source_sha256=sha256_text("hello"),
            )
        ],
    )
    path = tmp_path / "audio_manifest.json"
    manifest.save(path)
    loaded = load_manifest(path)
    assert loaded.project_id == "test"
    assert len(loaded.chapters) == 1
    assert loaded.chapters[0].status == TTS_STATUS_PENDING


def test_manifest_status_payload_counts():
    manifest = TtsManifest(
        project_id="test",
        source_mode="cn_chapters_dir",
        source_path="data/cn_chapters",
        output_dir="data/audio_projects/default",
        created_at=now_iso(),
        updated_at=now_iso(),
        chapters=[
            TtsChapter(
                index=1,
                title="a",
                source_path="a.txt",
                source_sha256="x",
                status="done",
            ),
            TtsChapter(
                index=2,
                title="b",
                source_path="b.txt",
                source_sha256="y",
                status="pending",
            ),
        ],
    )
    payload = manifest_status_payload(manifest)
    assert payload["total"] == 2
    assert payload["done"] == 1
    assert payload["pending"] == 1
    assert payload["chapters"][0] == chapter_summary(manifest.chapters[0])
