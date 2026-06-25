import wave
from pathlib import Path

from requests.exceptions import ChunkedEncodingError
import pytest

from youshengshu_tts.config import CosyVoiceHttpConfig
from youshengshu_tts.exceptions import TtsProviderError
from youshengshu_tts.providers.cosyvoice_http import CosyVoiceHttpProvider


def test_write_pcm_as_wav(tmp_path):
    provider = CosyVoiceHttpProvider(CosyVoiceHttpConfig())
    pcm = b"\x00\x00" * 1000
    out = tmp_path / "out.wav"

    provider._write_pcm_as_wav(pcm, out)

    with wave.open(str(out), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getframerate() == 22050
        assert wav.getnframes() == 1000


def test_write_pcm_as_wav_rejects_empty_pcm(tmp_path):
    provider = CosyVoiceHttpProvider(CosyVoiceHttpConfig())
    with pytest.raises(TtsProviderError):
        provider._write_pcm_as_wav(b"", tmp_path / "empty.wav")


def test_write_pcm_as_wav_rejects_odd_length_pcm(tmp_path):
    provider = CosyVoiceHttpProvider(CosyVoiceHttpConfig())
    with pytest.raises(TtsProviderError):
        provider._write_pcm_as_wav(b"\x00", tmp_path / "odd.wav")


class FakeBrokenStreamResponse:
    status_code = 200
    text = ""

    def iter_content(self, chunk_size):
        raise ChunkedEncodingError("Response ended prematurely")


def test_chunked_encoding_error_reports_gpu_server_failure(monkeypatch, tmp_path):
    def fake_post(*args, **kwargs):
        return FakeBrokenStreamResponse()

    monkeypatch.setattr("requests.post", fake_post)

    provider = CosyVoiceHttpProvider(CosyVoiceHttpConfig(max_retries=1))

    with pytest.raises(TtsProviderError) as exc:
        provider.synthesize_to_file("你好。", tmp_path / "out.wav")

    message = str(exc.value)
    assert "GPU 生成流被服务端提前中断" in message
    assert "CUDA" in message or "torch" in message
