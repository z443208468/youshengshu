from youshengshu_tts.config import TtsSegmentationConfig
from youshengshu_tts.text_segmenter import split_text_to_segments


def test_split_chinese_paragraph_into_segments():
    text = "第一句很短。" + "第二句也很短。" + "第三句继续。" * 20
    cfg = TtsSegmentationConfig(target_chars_max=50, hard_chars_max=80)
    segments = split_text_to_segments(text, cfg)
    assert len(segments) >= 2
    assert all(len(seg) <= cfg.hard_chars_max for seg in segments)


def test_segments_respect_hard_limit():
    long_sentence = "这是一段非常长的中文句子，" * 50
    cfg = TtsSegmentationConfig()
    segments = split_text_to_segments(long_sentence, cfg)
    assert segments
    assert all(len(seg) <= cfg.hard_chars_max for seg in segments)


def test_short_sentences_merge():
    text = "短句一。" + "短句二。" + "短句三。"
    cfg = TtsSegmentationConfig(target_chars_min=10, target_chars_max=180, hard_chars_max=240)
    segments = split_text_to_segments(text, cfg)
    assert len(segments) == 1


def test_quote_after_punctuation_preserved():
    text = '他说：“你好。”然后离开了。'
    cfg = TtsSegmentationConfig()
    segments = split_text_to_segments(text, cfg)
    joined = "".join(segments)
    assert "你好。”" in joined or any("你好。”" in seg for seg in segments)
