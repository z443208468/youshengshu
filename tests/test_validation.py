import pytest

from youshengshu.exceptions import TranslationValidationError
from youshengshu.validation import validate_translation_chunk


def test_validation_allows_i_cannot_and_i_am_unable_phrases():
    translated = (
        "我无法原谅你。\n\n"
        "我不能就这样离开。\n\n"
        "她低声说：我无法做到。\n\n"
        "他说，我不能接受这种结局。"
    )

    validate_translation_chunk("source", translated)


def test_validation_does_not_fail_on_refusal_like_text():
    translated = (
        "抱歉，我无法帮助完成这个翻译。\n\n"
        "作为AI语言模型，我不能提供该内容。\n\n"
        "但这些文字现在只会作为译文文本保存，不会触发程序失败。"
    )

    validate_translation_chunk("source", translated)


def test_validation_rejects_empty_translation():
    with pytest.raises(TranslationValidationError):
        validate_translation_chunk("source", "   ")


def test_validation_warns_but_does_not_fail_on_low_chinese_ratio():
    translated = "This is still mostly English text. " * 20

    with pytest.warns(UserWarning):
        validate_translation_chunk("source", translated)
