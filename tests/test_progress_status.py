from youshengshu.progress import (
    TranslationManifest,
    ManifestChapter,
    TRANSLATION_STATUS_DONE,
    TRANSLATION_STATUS_FAILED,
)


def test_done_status_clears_previous_error():
    manifest = TranslationManifest(
        source_file="test.txt",
        chapters=[
            ManifestChapter(
                index=1,
                title="Test",
                en_path="data/en_chapters/chapter_001_en.txt",
                source_sha256="sha",
            )
        ],
    )
    ch = manifest.chapters[0]
    ch.translation_status = TRANSLATION_STATUS_FAILED
    ch.error = "old error"

    manifest.set_chapter_status(1, TRANSLATION_STATUS_DONE, model="m", chunk_count=1)

    assert ch.error is None
    assert ch.translation_status == TRANSLATION_STATUS_DONE
