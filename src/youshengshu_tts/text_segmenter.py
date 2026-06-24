from __future__ import annotations

import re

from .config import TtsSegmentationConfig


SENTENCE_END = set("。！？!?；;")
RIGHT_QUOTES = set("”」』》）】]")
SOFT_BREAK_CHARS = "，、, "


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u3000", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_paragraphs(text: str) -> list[str]:
    paragraphs = [item.strip() for item in re.split(r"\n\s*\n", text)]
    return [item for item in paragraphs if item]


def split_by_sentence_punctuation(paragraph: str) -> list[str]:
    result: list[str] = []
    start = 0
    index = 0

    while index < len(paragraph):
        char = paragraph[index]

        if char in SENTENCE_END:
            end = index + 1

            while end < len(paragraph) and paragraph[end] in RIGHT_QUOTES:
                end += 1

            sentence = paragraph[start:end].strip()
            if sentence:
                result.append(sentence)

            start = end
            index = end
            continue

        if char == "…" and index + 1 < len(paragraph) and paragraph[index + 1] == "…":
            end = index + 2

            while end < len(paragraph) and paragraph[end] in RIGHT_QUOTES:
                end += 1

            sentence = paragraph[start:end].strip()
            if sentence:
                result.append(sentence)

            start = end
            index = end
            continue

        index += 1

    tail = paragraph[start:].strip()
    if tail:
        result.append(tail)

    return result


def join_with_natural_space(left: str, right: str) -> str:
    left = left.strip()
    right = right.strip()

    if not left:
        return right

    if not right:
        return left

    if left.endswith("\n") or right.startswith("\n"):
        return f"{left}{right}"

    return f"{left}{right}"


def force_split_by_hard_limit(text: str, hard_chars_max: int) -> list[str]:
    text = text.strip()
    if not text:
        return []

    return [
        text[index : index + hard_chars_max].strip()
        for index in range(0, len(text), hard_chars_max)
        if text[index : index + hard_chars_max].strip()
    ]


def split_long_sentence(sentence: str, hard_chars_max: int) -> list[str]:
    sentence = sentence.strip()

    if len(sentence) <= hard_chars_max:
        return [sentence] if sentence else []

    pieces: list[str] = []
    current = ""

    for char in sentence:
        current += char

        if len(current) >= hard_chars_max:
            split_index = max(current.rfind(mark) for mark in SOFT_BREAK_CHARS)

            if split_index > 0:
                pieces.append(current[: split_index + 1].strip())
                current = current[split_index + 1 :].strip()
            else:
                pieces.append(current[:hard_chars_max].strip())
                current = current[hard_chars_max:].strip()

    if current:
        pieces.append(current.strip())

    final: list[str] = []
    for piece in pieces:
        if len(piece) <= hard_chars_max:
            final.append(piece)
        else:
            final.extend(force_split_by_hard_limit(piece, hard_chars_max))

    return [item for item in final if item]


def split_text_to_segments(text: str, cfg: TtsSegmentationConfig) -> list[str]:
    normalized = normalize_text(text)

    if not normalized:
        return []

    paragraphs = split_paragraphs(normalized)

    sentences: list[str] = []
    for paragraph in paragraphs:
        sentences.extend(split_by_sentence_punctuation(paragraph))

    segments: list[str] = []
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        if len(sentence) > cfg.hard_chars_max:
            pieces = split_long_sentence(sentence, cfg.hard_chars_max)
        else:
            pieces = [sentence]

        for piece in pieces:
            if not piece:
                continue

            candidate = join_with_natural_space(current, piece)

            if len(candidate) <= cfg.target_chars_max:
                current = candidate
                continue

            if current:
                segments.append(current)
                current = piece
            else:
                segments.extend(force_split_by_hard_limit(piece, cfg.hard_chars_max))
                current = ""

            if len(current) > cfg.hard_chars_max:
                segments.extend(force_split_by_hard_limit(current, cfg.hard_chars_max))
                current = ""

    if current:
        segments.append(current)

    final: list[str] = []
    for segment in segments:
        segment = segment.strip()
        if not segment:
            continue

        if len(segment) <= cfg.hard_chars_max:
            final.append(segment)
        else:
            final.extend(force_split_by_hard_limit(segment, cfg.hard_chars_max))

    return final
