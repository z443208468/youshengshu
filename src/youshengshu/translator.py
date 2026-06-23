import math
from dataclasses import dataclass
from pathlib import Path

from .config import AppConfig
from .exceptions import TranslationValidationError, ContextOverflowError
from .lmstudio_client import LMStudioClient
from .progress import (
    ManifestChapter,
    TranslationManifest,
    TRANSLATION_STATUS_PENDING,
    TRANSLATION_STATUS_IN_PROGRESS,
    TRANSLATION_STATUS_DONE,
    TRANSLATION_STATUS_FAILED,
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


def translate_chapter(
    chapter_record: ManifestChapter,
    config: AppConfig,
    client: LMStudioClient,
    manifest: TranslationManifest,
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

    manifest.set_chapter_status(
        chapter_record.index,
        TRANSLATION_STATUS_IN_PROGRESS,
    )

    batch_size = _validated_initial_batch_size(config)
    backoff_factor = float(config.chunking.overflow_backoff_factor)

    translated_batches: list[str] = []
    cursor = 0
    batch_count = 0

    cn_partial_path = Path(chapter_record.cn_path.replace("_cn.txt", "_cn.partial.txt"))
    cn_tmp_path = Path(chapter_record.cn_path + ".tmp")
    cn_final_path = Path(chapter_record.cn_path)

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
                manifest.set_chapter_status(
                    chapter_record.index,
                    TRANSLATION_STATUS_FAILED,
                    error=error,
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
            manifest.set_chapter_status(
                chapter_record.index,
                TRANSLATION_STATUS_FAILED,
                error=str(e),
            )
            raise

        if config.translation.strip_model_preamble:
            result = strip_known_preambles(result)

        try:
            validate_translation_chunk(source_chunk, result)
        except TranslationValidationError as e:
            manifest.set_chapter_status(
                chapter_record.index,
                TRANSLATION_STATUS_FAILED,
                error=str(e),
            )
            raise

        translated_batches.append(result)
        batch_count += 1
        cursor += len(batch)

        if config.translation.write_partial_file:
            cn_partial_path.parent.mkdir(parents=True, exist_ok=True)
            cn_partial_path.write_text("\n\n".join(translated_batches), encoding="utf-8")

    final_text = "\n\n".join(translated_batches)
    cn_final_path.parent.mkdir(parents=True, exist_ok=True)
    cn_tmp_path.write_text(final_text, encoding="utf-8")
    cn_tmp_path.replace(cn_final_path)

    if cn_partial_path.exists():
        cn_partial_path.unlink()

    manifest.set_chapter_status(
        chapter_record.index,
        TRANSLATION_STATUS_DONE,
        model=model_id,
        chunk_count=batch_count,
    )

    return TranslationResult(
        chapter_index=chapter_record.index,
        cn_path=str(cn_final_path),
        chunk_count=batch_count,
        model_id=model_id,
    )


def run_translation_pipeline(
    config: AppConfig,
    client: LMStudioClient,
    manifest: TranslationManifest,
    max_chapters: int = 0,
) -> list[TranslationResult]:
    """Translate all pending/failed chapters sequentially.

    Process chapters in order. Each chapter is attempted at most once per
    call: on failure the manifest status is set to 'failed' and the error is
    persisted; on success the manifest status is set to 'done'.
    """

    results: list[TranslationResult] = []
    manifest_path = Path(config.paths.manifest_file)

    chapters_to_translate: list[ManifestChapter] = []
    for ch in manifest.chapters:
        if ch.translation_status in (
            TRANSLATION_STATUS_PENDING,
            TRANSLATION_STATUS_FAILED,
        ):
            chapters_to_translate.append(ch)

    if not chapters_to_translate:
        print("所有章节已完成，无需翻译。")
        return results

    if max_chapters > 0:
        chapters_to_translate = chapters_to_translate[:max_chapters]

    for chapter in chapters_to_translate:
        print(f"\n翻译第 {chapter.index} 章: {chapter.title or ''}")

        try:
            result = translate_chapter(chapter, config, client, manifest)
            results.append(result)
            print(f"  完成: {result.cn_path} ({result.chunk_count} chunks)")
        except Exception as e:
            print(f"  [ERROR] 第 {chapter.index} 章翻译失败: {e}")
        finally:
            manifest.save(manifest_path)

    return results
