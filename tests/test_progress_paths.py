from pathlib import Path

from youshengshu.chapter_splitter import ChapterFileRecord
from youshengshu.progress import (
    TranslationManifest,
    ManifestChapter,
    expected_cn_path_for_en_path,
    expected_partial_path_for_cn_path,
    expected_resume_state_path_for_cn_path,
)


def test_expected_cn_path_for_en_path():
    cn = expected_cn_path_for_en_path(
        "data/en_chapters/chapter_001_en.txt",
        "data/cn_chapters",
    )
    assert Path(cn) == Path("data/cn_chapters/chapter_001_cn.txt")


def test_expected_partial_and_resume_paths():
    cn = "data/cn_chapters/chapter_001_cn.txt"
    assert Path(expected_partial_path_for_cn_path(cn)) == Path(
        "data/cn_chapters/chapter_001_cn.partial.txt"
    )
    assert Path(expected_resume_state_path_for_cn_path(cn)) == Path(
        "data/cn_chapters/chapter_001_cn.resume.json"
    )


def test_create_manifest_uses_cn_chapters_dir(tmp_path):
    records = [
        ChapterFileRecord(
            index=1,
            title="A",
            filename="chapter_001_en.txt",
            filepath=str(tmp_path / "en" / "chapter_001_en.txt"),
            sha256="sha",
        )
    ]

    manifest = TranslationManifest.create_from_records(
        source_file=str(tmp_path / "input.txt"),
        records=records,
        cn_chapters_dir=str(tmp_path / "cn"),
    )

    ch = manifest.chapters[0]
    assert Path(ch.cn_path).parent == tmp_path / "cn"
    assert Path(ch.cn_path).name == "chapter_001_cn.txt"


def test_normalize_cn_paths_moves_legacy_cn_file(tmp_path):
    en_dir = tmp_path / "en"
    cn_dir = tmp_path / "cn"
    en_dir.mkdir()
    cn_dir.mkdir()

    old_cn = en_dir / "chapter_001_cn.txt"
    old_cn.write_text("旧译文", encoding="utf-8")

    manifest = TranslationManifest(
        source_file=str(tmp_path / "input.txt"),
        chapters=[
            ManifestChapter(
                index=1,
                title="A",
                en_path=str(en_dir / "chapter_001_en.txt"),
                cn_path=str(old_cn),
                source_sha256="sha",
            )
        ],
    )

    changed = manifest.normalize_cn_paths(str(cn_dir))

    assert changed == [1]
    assert not old_cn.exists()
    assert (cn_dir / "chapter_001_cn.txt").exists()
    assert manifest.chapters[0].cn_path == str(cn_dir / "chapter_001_cn.txt")
