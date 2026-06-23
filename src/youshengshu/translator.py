import math
from dataclasses import dataclass
from pathlib import Path

from .config import AppConfig
from .exceptions import (
    TranslationValidationError,
    ContextOverflowError,
    TranslationStateError,
    TranslationPipelineStoppedError,
)
from .lmstudio_client import LMStudioClient
from .progress import (
    ManifestChapter,
    TranslationManifest,
    TRANSLATION_STATUS_IN_PROGRESS,
    TRANSLATION_STATUS_DONE,
    TRANSLATION_STATUS_FAILED,
    TRANSLATION_STATUS_PENDING,
    expected_partial_path_for_cn_path,
    expected_resume_state_path_for_cn_path,
)
from .resume_state import (
    new_resume_state,
    load_resume_state,
    save_resume_state_atomic,
    validate_resume_state,
    append_translated_batch,
    render_partial_text,
)
from .text_utils import split_paragraph_blocks
from .validation import strip_known_preambles, validate_translation_chunk

SYSTEM_PROMPT = "你是严格的英译中小说翻译引擎。你只输出中文译文，不输出解释、分析、总结或额外说明。"

USER_PROMPT_TEMPLATE = """你现在执行的是小说英译中任务，不是角色扮演，不是续写。

任务：
把下面英文小说片段逐段翻译成自然流畅的中文。

硬性规则：
1. 只翻译，不续写，不补充剧情，不改写剧情。
2. 不要总结，不要解释，不要评价。
3. 不要增加原文没有的信息。
4. 不要删除任何句子。
5. 保留段落结构。
6. 保留对白、动作描写、心理描写的顺序。
7. 只输出中文译文。
8. 不要输出"好的""以下是翻译""译文如下"。
9. 不要输出英文原文。
10. 人名、地名、术语必须按译名表处理。

译名表：
Subaru = 昴
Natsuki Subaru = 菜月昴
Emilia = 爱蜜莉雅
Rem = 雷姆
Ram = 拉姆
Beatrice = 碧翠丝
Betty = 贝蒂
Beako =贝阿朵
Roswaal = 罗兹瓦尔
Otto = 奥托
Garfiel = 加菲尔
Felt = 菲鲁特
Reinhard = 莱因哈特
Crusch = 库珥修
Felix = 菲利克斯
Ferris = 菲利克斯
Wilhelm = 威尔海姆
Anastasia = 安娜塔西亚
Julius = 尤里乌斯
Priscilla = 普莉希拉
Al = 阿尔
Echidna = 艾姬多娜
Witch of Envy = 嫉妒魔女
Return by Death = 死亡回归
Sage Candidate = 贤者候补
Priestella = 普利斯提拉
Watergate City = 水门都市
Sanctuary = 圣域
Dragon Carriage = 龙车

风格：
- 中文要自然，适合轻小说有声书朗读。
- 不要文绉绉。
- 对白可以口语化，但不能改变意思。
- 昴的语气可以口语、跳脱、犯贱一点。
- 爱蜜莉雅的语气温柔、认真、略天然。
- 碧翠丝的语气傲娇、别扭，可以保留"……的说"，但不要每句都机械重复。
- 雷姆的语气温柔、虔诚、克制。
- 拉姆的语气毒舌、冷淡。
- 普莉希拉的语气高傲、轻蔑。
- 安娜塔西亚的语气精明、有商人感。

下面是原文片段：

{source_chunk}"""


@dataclass
class TranslationResult:
    chapter_index: int
    cn_path: str
    chunk_count: int
    model_id: str


def _validated_initial_batch_size(config: AppConfig) -> int:
    size = int(config.chunking.initial_paragraphs_per_batch)
    min_size = int(config.chunking.min_paragraphs_per_batch)

    if min_size != 1:
        raise ValueError("chunking.min_paragraphs_per_batch 必须为 1。")
    if size < 1:
        raise ValueError("chunking.initial_paragraphs_per_batch 必须 >= 1。")
    if not (0 < float(config.chunking.overflow_backoff_factor) < 1):
        raise ValueError("chunking.overflow_backoff_factor 必须在 (0, 1) 范围内。")

    return size


def _reduce_batch_size(current: int, factor: float) -> int:
    if current <= 1:
        return 1

    reduced = max(1, math.floor(current * factor))
    if reduced >= current:
        reduced = current - 1

    return max(1, reduced)


def _save_failure_progress(
    chapter_record: ManifestChapter,
    manifest: TranslationManifest,
    manifest_path: Path,
    state,
    cn_partial_path: Path,
    resume_state_path: Path,
    error: str,
) -> None:
    if state is not None:
        chapter_record.translated_paragraph_count = state.completed_paragraph_count
        chapter_record.translated_batch_count = state.completed_batch_count
        chapter_record.chunk_count = state.completed_batch_count
        chapter_record.partial_path = (
            str(cn_partial_path) if cn_partial_path.exists() else None
        )
        chapter_record.resume_state_path = (
            str(resume_state_path) if resume_state_path.exists() else None
        )

    manifest.set_chapter_status(
        chapter_record.index,
        TRANSLATION_STATUS_FAILED,
        error=error,
    )
    manifest.save(manifest_path)


def translate_chapter(
    chapter_record: ManifestChapter,
    config: AppConfig,
    client: LMStudioClient,
    manifest: TranslationManifest,
    manifest_path: Path,
) -> TranslationResult:
    """Translate a single chapter. Updates manifest in-place."""

    en_path = Path(chapter_record.en_path)
    if not en_path.exists():
        raise FileNotFoundError(f"英文章节文件不存在: {en_path}")

    chapter_text = en_path.read_text(encoding="utf-8")
    paragraphs = split_paragraph_blocks(chapter_text)
    if not paragraphs:
        raise ValueError("章节没有可翻译段落。")

    model_id = client._resolved_model_id or "unknown"

    cn_final_path = Path(chapter_record.cn_path)
    cn_partial_path = Path(expected_partial_path_for_cn_path(chapter_record.cn_path))
    resume_state_path = Path(expected_resume_state_path_for_cn_path(chapter_record.cn_path))
    cn_tmp_path = Path(chapter_record.cn_path + ".tmp")

    chapter_record.source_paragraph_count = len(paragraphs)
    chapter_record.partial_path = str(cn_partial_path)
    chapter_record.resume_state_path = str(resume_state_path)

    manifest.set_chapter_status(
        chapter_record.index,
        TRANSLATION_STATUS_IN_PROGRESS,
    )
    manifest.save(manifest_path)

    state = load_resume_state(resume_state_path)

    if state is None:
        state = new_resume_state(
            chapter_index=chapter_record.index,
            chapter_source_sha256=chapter_record.source_sha256,
            total_paragraphs=len(paragraphs),
        )

        legacy_partial = cn_partial_path
        if legacy_partial.exists():
            legacy_path = legacy_partial.with_suffix(legacy_partial.suffix + ".legacy")
            legacy_partial.replace(legacy_path)
            print(
                f"  检测到旧 partial 文件但没有 resume state，已保留为: {legacy_path}",
                flush=True,
            )
    else:
        validate_resume_state(
            state,
            chapter_index=chapter_record.index,
            chapter_source_sha256=chapter_record.source_sha256,
            paragraphs=paragraphs,
        )

    cursor = state.completed_paragraph_count
    batch_count = state.completed_batch_count

    chapter_record.translated_paragraph_count = cursor
    chapter_record.translated_batch_count = batch_count
    chapter_record.chunk_count = batch_count
    manifest.save(manifest_path)

    print(
        f"  Resume state: chapter_index={chapter_record.index}, "
        f"cursor={cursor}, total_paragraphs={len(paragraphs)}, "
        f"completed_batches={batch_count}",
        flush=True,
    )

    batch_size = _validated_initial_batch_size(config)
    backoff_factor = float(config.chunking.overflow_backoff_factor)

    while cursor < len(paragraphs):
        batch = paragraphs[cursor : cursor + batch_size]
        source_chunk = "\n\n".join(batch)

        print(
            f"  Paragraph batch: chapter_index={chapter_record.index}, "
            f"cursor={cursor}, "
            f"batch_size={len(batch)}, "
            f"paragraphs_total={len(paragraphs)}",
            flush=True,
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": USER_PROMPT_TEMPLATE.replace("{source_chunk}", source_chunk),
            },
        ]

        try:
            result = client.translate(messages)

        except ContextOverflowError as e:
            if batch_size <= 1:
                error = (
                    "单个段落超过 LM Studio 当前上下文能力，程序不会拆分段落。"
                    f" chapter_index={chapter_record.index}, "
                    f"paragraph_index={cursor}, "
                    f"paragraph_chars={len(batch[0])}, "
                    f"error={e}"
                )
                _save_failure_progress(
                    chapter_record,
                    manifest,
                    manifest_path,
                    state,
                    cn_partial_path,
                    resume_state_path,
                    error,
                )
                raise ContextOverflowError(error) from e

            new_batch_size = _reduce_batch_size(batch_size, backoff_factor)
            print(
                f"  Context overflow, reduce paragraph batch size: "
                f"{batch_size} -> {new_batch_size}",
                flush=True,
            )
            batch_size = new_batch_size
            continue

        except Exception as e:
            _save_failure_progress(
                chapter_record,
                manifest,
                manifest_path,
                state,
                cn_partial_path,
                resume_state_path,
                str(e),
            )
            raise

        if config.translation.strip_model_preamble:
            result = strip_known_preambles(result)

        try:
            validate_translation_chunk(source_chunk, result)
        except TranslationValidationError as e:
            _save_failure_progress(
                chapter_record,
                manifest,
                manifest_path,
                state,
                cn_partial_path,
                resume_state_path,
                str(e),
            )
            raise

        start = cursor
        end = cursor + len(batch)

        append_translated_batch(
            state=state,
            paragraphs=paragraphs,
            start=start,
            end=end,
            translated_text=result,
        )

        cursor = state.completed_paragraph_count
        batch_count = state.completed_batch_count

        save_resume_state_atomic(state, resume_state_path)

        if config.translation.write_partial_file:
            cn_partial_path.parent.mkdir(parents=True, exist_ok=True)
            cn_partial_path.write_text(render_partial_text(state), encoding="utf-8")

        chapter_record.translated_paragraph_count = cursor
        chapter_record.translated_batch_count = batch_count
        chapter_record.chunk_count = batch_count
        chapter_record.partial_path = str(cn_partial_path)
        chapter_record.resume_state_path = str(resume_state_path)

        manifest.save(manifest_path)

    final_text = render_partial_text(state)

    cn_final_path.parent.mkdir(parents=True, exist_ok=True)
    cn_tmp_path.write_text(final_text, encoding="utf-8")
    cn_tmp_path.replace(cn_final_path)

    if cn_partial_path.exists():
        cn_partial_path.unlink()

    if resume_state_path.exists():
        resume_state_path.unlink()

    chapter_record.translated_paragraph_count = len(paragraphs)
    chapter_record.source_paragraph_count = len(paragraphs)
    chapter_record.translated_batch_count = state.completed_batch_count
    chapter_record.partial_path = None
    chapter_record.resume_state_path = None

    manifest.set_chapter_status(
        chapter_record.index,
        TRANSLATION_STATUS_DONE,
        model=model_id,
        chunk_count=state.completed_batch_count,
    )
    manifest.save(manifest_path)

    return TranslationResult(
        chapter_index=chapter_record.index,
        cn_path=str(cn_final_path),
        chunk_count=state.completed_batch_count,
        model_id=model_id,
    )


def run_translation_pipeline(
    config: AppConfig,
    client: LMStudioClient,
    manifest: TranslationManifest,
    max_chapters: int = 0,
    chapter_index: int = 0,
) -> list[TranslationResult]:
    """Translate pending/failed/in_progress chapters sequentially."""

    results: list[TranslationResult] = []
    manifest_path = Path(config.paths.manifest_file)

    eligible_statuses = (
        TRANSLATION_STATUS_PENDING,
        TRANSLATION_STATUS_FAILED,
        TRANSLATION_STATUS_IN_PROGRESS,
    )

    if chapter_index > 0:
        chapter = manifest.get_chapter_by_index(chapter_index)
        if chapter is None:
            raise ValueError(f"章节不存在: {chapter_index}")

        if chapter.translation_status == TRANSLATION_STATUS_DONE:
            print(f"第 {chapter_index} 章已完成，未重新翻译。")
            return []

        chapters_to_translate = [chapter]
        print(f"Selected chapter by index: {chapter_index}", flush=True)
    else:
        chapters_to_translate = [
            ch for ch in manifest.chapters
            if ch.translation_status in eligible_statuses
        ]

        if max_chapters > 0:
            chapters_to_translate = chapters_to_translate[:max_chapters]

        if chapter_index <= 0 and max_chapters == 1 and chapters_to_translate:
            ch = chapters_to_translate[0]
            print(
                f"Selected next pending chapter: {ch.index} "
                f"status={ch.translation_status} "
                f"translated_paragraph_count={ch.translated_paragraph_count} "
                f"partial_path={ch.partial_path or '-'}",
                flush=True,
            )

    if not chapters_to_translate:
        print("所有章节已完成，无需翻译。")
        return results

    for chapter in chapters_to_translate:
        print(f"\n翻译第 {chapter.index} 章: {chapter.title or ''}")

        try:
            result = translate_chapter(
                chapter,
                config,
                client,
                manifest,
                manifest_path,
            )
            results.append(result)
            print(f"  完成: {result.cn_path} ({result.chunk_count} batches)")
        except Exception as e:
            manifest.save(manifest_path)
            print(f"  [ERROR] 第 {chapter.index} 章翻译失败: {e}")
            print("  已停止后续章节翻译。修复问题后再次执行将从该章断点继续。")
            raise TranslationPipelineStoppedError(
                f"第 {chapter.index} 章翻译失败，已停止后续章节。原始错误: {e}"
            ) from e

        manifest.save(manifest_path)

    return results
