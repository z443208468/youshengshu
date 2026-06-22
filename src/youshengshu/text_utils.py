import math
import re
from dataclasses import dataclass

from .config import ChunkingConfig
from .exceptions import ConfigError

SENTENCE_SPLIT_RE = re.compile(r"([.!?。！？][\"'”’）)]?\s+)")


@dataclass
class ChunkBudget:
    context_tokens: int
    prompt_tokens: int
    reserved_output_tokens: int
    safety_ratio: float
    available_source_tokens: int


@dataclass
class ChunkDebugInfo:
    index: int
    estimated_tokens: int
    chars: int
    paragraphs: int


def normalize_newlines(text: str) -> str:
    """Normalize \\r\\n and \\r to \\n."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def estimate_tokens(
    text: str,
    english_chars_per_token: float = 4.0,
    cjk_chars_per_token: float = 1.2,
) -> int:
    """Roughly estimate token count without a real tokenizer."""
    if not text or not text.strip():
        return 1
    ascii_like_chars = sum(1 for ch in text if ord(ch) < 128 and not ch.isspace())
    total_non_whitespace = sum(1 for ch in text if not ch.isspace())
    cjk_like_chars = total_non_whitespace - ascii_like_chars

    estimated = math.ceil(
        ascii_like_chars / english_chars_per_token
        + cjk_like_chars / cjk_chars_per_token
    )
    return max(1, estimated)


def estimate_with_config(text: str, config: ChunkingConfig) -> int:
    return estimate_tokens(
        text,
        config.english_chars_per_token,
        config.cjk_chars_per_token,
    )


def calculate_chunk_budget(
    config: ChunkingConfig,
    prompt_text: str,
) -> ChunkBudget:
    prompt_tokens = estimate_tokens(
        prompt_text,
        config.english_chars_per_token,
        config.cjk_chars_per_token,
    )

    raw_available = config.context_tokens - prompt_tokens - config.reserved_output_tokens
    available_source_tokens = math.floor(raw_available * config.safety_ratio)

    if config.context_tokens <= 0:
        raise ConfigError("chunking.context_tokens 必须大于 0。")

    if config.reserved_output_tokens <= 0:
        raise ConfigError("chunking.reserved_output_tokens 必须大于 0。")

    if not (0 < config.safety_ratio <= 1):
        raise ConfigError("chunking.safety_ratio 必须在 (0, 1] 范围内。")

    if available_source_tokens <= 0:
        raise ConfigError(
            "可用 source token 预算不足。"
            f"context_tokens={config.context_tokens}, "
            f"prompt_tokens≈{prompt_tokens}, "
            f"reserved_output_tokens={config.reserved_output_tokens}, "
            f"safety_ratio={config.safety_ratio}, "
            f"available_source_tokens={available_source_tokens}。"
        )

    return ChunkBudget(
        context_tokens=config.context_tokens,
        prompt_tokens=prompt_tokens,
        reserved_output_tokens=config.reserved_output_tokens,
        safety_ratio=config.safety_ratio,
        available_source_tokens=available_source_tokens,
    )


def split_paragraph_blocks(text: str) -> list[str]:
    normalized = normalize_newlines(text).strip()
    if not normalized:
        return []

    blocks = re.split(r"\n\s*\n+", normalized)
    return [block.strip() for block in blocks if block.strip()]


def split_sentence_blocks(paragraph: str) -> list[str]:
    text = paragraph.strip()
    if not text:
        return []

    parts = SENTENCE_SPLIT_RE.split(text)
    sentences: list[str] = []
    current = ""

    for part in parts:
        current += part
        if SENTENCE_SPLIT_RE.fullmatch(part):
            if current.strip():
                sentences.append(current.strip())
            current = ""

    if current.strip():
        sentences.append(current.strip())

    return sentences


def split_word_blocks(sentence: str) -> list[str]:
    words = sentence.strip().split()
    return [w for w in words if w]


def describe_chunks(
    chunks: list[str],
    config: ChunkingConfig,
) -> list[ChunkDebugInfo]:
    infos: list[ChunkDebugInfo] = []

    for i, chunk in enumerate(chunks):
        paragraphs = split_paragraph_blocks(chunk)
        infos.append(
            ChunkDebugInfo(
                index=i + 1,
                estimated_tokens=estimate_with_config(chunk, config),
                chars=len(chunk),
                paragraphs=len(paragraphs),
            )
        )

    return infos


def split_single_oversized_word_explicitly_enabled(
    word: str,
    config: ChunkingConfig,
    budget: ChunkBudget,
) -> list[str]:
    parts: list[str] = []
    start = 0

    while start < len(word):
        low = start + 1
        high = len(word)
        best = low

        while low <= high:
            mid = (low + high) // 2
            candidate = word[start:mid]
            if estimate_with_config(candidate, config) <= budget.available_source_tokens:
                best = mid
                low = mid + 1
            else:
                high = mid - 1

        parts.append(word[start:best])
        start = best

    return parts


def split_oversized_sentence_by_words(
    sentence: str,
    config: ChunkingConfig,
    budget: ChunkBudget,
) -> list[str]:
    words = split_word_blocks(sentence)

    if not words:
        raise ConfigError(
            "存在无法按空白切分的超长句子。"
            "为避免破坏原文，默认不进行字符硬切。"
        )

    result: list[str] = []
    current_words: list[str] = []

    def word_text(parts: list[str]) -> str:
        return " ".join(parts).strip()

    def flush_words() -> None:
        nonlocal current_words
        if current_words:
            result.append(word_text(current_words))
            current_words = []

    for word in words:
        word_tokens = estimate_with_config(word, config)

        if word_tokens > budget.available_source_tokens:
            flush_words()

            if config.allow_word_split:
                result.extend(
                    split_single_oversized_word_explicitly_enabled(
                        word=word,
                        config=config,
                        budget=budget,
                    )
                )
            else:
                preview = word[:120]
                raise ConfigError(
                    "存在单个不可分片段超过当前 source token 预算。"
                    "为避免破坏单词/URL/专有名词，程序不会默认在中间硬切。"
                    f" word_estimated_tokens≈{word_tokens}, "
                    f"available_source_tokens={budget.available_source_tokens}, "
                    f"preview={preview!r}。"
                    "解决方式：提高 chunking.context_tokens，降低 reserved_output_tokens，"
                    "或手动清理异常超长片段；确实要硬切时，显式设置 allow_word_split=true。"
                )
        else:
            candidate = word_text(current_words + [word])
            if estimate_with_config(candidate, config) <= budget.available_source_tokens:
                current_words.append(word)
            else:
                flush_words()
                current_words = [word]

    flush_words()
    return result


def split_oversized_paragraph_by_boundaries(
    paragraph: str,
    config: ChunkingConfig,
    budget: ChunkBudget,
) -> list[str]:
    sentences = split_sentence_blocks(paragraph)

    if not sentences:
        raise ConfigError("存在无法切分的空段落。")

    result: list[str] = []
    current_sentences: list[str] = []

    def sentence_text(parts: list[str]) -> str:
        return " ".join(parts).strip()

    def flush_sentences() -> None:
        nonlocal current_sentences
        if current_sentences:
            result.append(sentence_text(current_sentences))
            current_sentences = []

    for sentence in sentences:
        sentence_tokens = estimate_with_config(sentence, config)

        if sentence_tokens <= budget.available_source_tokens:
            candidate = sentence_text(current_sentences + [sentence])
            if estimate_with_config(candidate, config) <= budget.available_source_tokens:
                current_sentences.append(sentence)
            else:
                flush_sentences()
                current_sentences = [sentence]
        else:
            flush_sentences()
            word_chunks = split_oversized_sentence_by_words(
                sentence=sentence,
                config=config,
                budget=budget,
            )
            result.extend(word_chunks)

    flush_sentences()

    return result


def split_text_for_translation(
    text: str,
    config: ChunkingConfig,
    prompt_text: str,
) -> list[str]:
    """Split source text into chunks that fit within the model's context budget."""
    budget = calculate_chunk_budget(config, prompt_text)
    paragraphs = split_paragraph_blocks(text)

    if not paragraphs:
        raise ConfigError("输入文本没有可翻译段落。")

    chunks: list[str] = []
    current_parts: list[str] = []

    def flush_current() -> None:
        nonlocal current_parts
        if current_parts:
            chunks.append("\n\n".join(current_parts))
            current_parts = []

    for paragraph in paragraphs:
        if estimate_with_config(paragraph, config) <= budget.available_source_tokens:
            candidate_parts = current_parts + [paragraph]
            candidate = "\n\n".join(candidate_parts)

            if estimate_with_config(candidate, config) <= budget.available_source_tokens:
                current_parts = candidate_parts
            else:
                flush_current()
                current_parts = [paragraph]
        else:
            flush_current()
            oversized_chunks = split_oversized_paragraph_by_boundaries(
                paragraph=paragraph,
                config=config,
                budget=budget,
            )
            chunks.extend(oversized_chunks)

    flush_current()

    if not chunks:
        raise ConfigError("切分后 chunk 列表为空，请检查输入文本。")

    for chunk in chunks:
        if estimate_with_config(chunk, config) > budget.available_source_tokens:
            raise ConfigError("内部错误：生成了超过预算的 chunk。")

    return chunks
