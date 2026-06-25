import time
import wave
from pathlib import Path

import requests
from requests.exceptions import ChunkedEncodingError, ConnectionError, ReadTimeout

from .base import TtsProvider, TtsProviderResult
from ..config import CosyVoiceHttpConfig
from ..exceptions import TtsProviderError


SUPPORTED_MODES = {"sft", "zero_shot", "cross_lingual", "instruct"}


class CosyVoiceHttpProvider(TtsProvider):
    def __init__(self, config: CosyVoiceHttpConfig):
        self.config = config

    def synthesize_to_file(self, text: str, output_path: Path) -> TtsProviderResult:
        if self.config.mode not in SUPPORTED_MODES:
            raise TtsProviderError(
                f"不支持的 CosyVoice mode: {self.config.mode}; "
                f"supported={sorted(SUPPORTED_MODES)}"
            )

        last_error: Exception | None = None

        for attempt in range(1, self.config.max_retries + 1):
            try:
                pcm_bytes = self._request_tts_pcm(text)
                self._write_pcm_as_wav(pcm_bytes, output_path)
                return TtsProviderResult(
                    output_path=str(output_path),
                    sample_rate=self.config.sample_rate,
                )
            except Exception as exc:
                last_error = exc
                if attempt < self.config.max_retries:
                    time.sleep(self.config.retry_sleep_seconds)

        raise TtsProviderError(
            f"CosyVoice TTS failed after {self.config.max_retries} attempts: {last_error}"
        )

    def _request_tts_pcm(self, text: str) -> bytes:
        base_url = self.config.base_url.rstrip("/")
        mode = self.config.mode
        url = f"{base_url}/inference_{mode}"

        data: dict[str, str] = {"tts_text": text}
        files = None
        opened_file = None

        try:
            if mode == "sft":
                data["spk_id"] = self.config.spk_id

            elif mode == "zero_shot":
                data["prompt_text"] = self.config.prompt_text
                prompt_path = self._require_prompt_wav()
                opened_file = prompt_path.open("rb")
                files = {
                    "prompt_wav": (
                        prompt_path.name,
                        opened_file,
                        "application/octet-stream",
                    )
                }

            elif mode == "cross_lingual":
                prompt_path = self._require_prompt_wav()
                opened_file = prompt_path.open("rb")
                files = {
                    "prompt_wav": (
                        prompt_path.name,
                        opened_file,
                        "application/octet-stream",
                    )
                }

            elif mode == "instruct":
                data["spk_id"] = self.config.spk_id
                data["instruct_text"] = self.config.instruct_text

            response = requests.post(
                url,
                data=data,
                files=files,
                timeout=self.config.request_timeout_seconds,
                stream=True,
            )

            if response.status_code != 200:
                body = response.text[:1000] if response.text else ""
                raise TtsProviderError(
                    f"CosyVoice HTTP {response.status_code}: {body}"
                )

            try:
                pcm = b"".join(response.iter_content(chunk_size=16000))
            except ChunkedEncodingError as exc:
                raise TtsProviderError(
                    "CosyVoice GPU 生成流被服务端提前中断。"
                    "当前最常见原因是服务端 CUDA/PyTorch/模型推理崩溃；"
                    "请检查 CosyVoice 服务日志中的 no kernel image / CUDA / torch 错误。"
                ) from exc
            except (ConnectionError, ReadTimeout) as exc:
                raise TtsProviderError(f"CosyVoice HTTP stream 读取失败: {exc}") from exc

            if not pcm:
                raise TtsProviderError("CosyVoice 返回空音频。")

            if len(pcm) % 2 != 0:
                raise TtsProviderError(
                    f"CosyVoice 返回的 PCM 长度不是 int16 对齐: {len(pcm)} bytes"
                )

            return pcm

        finally:
            if opened_file is not None:
                opened_file.close()

    def _require_prompt_wav(self) -> Path:
        path = Path(self.config.prompt_audio_path)
        if not path.exists():
            raise TtsProviderError(f"prompt_wav 不存在: {path}")
        if not path.is_file():
            raise TtsProviderError(f"prompt_wav 不是文件: {path}")
        return path

    def _write_pcm_as_wav(self, pcm_bytes: bytes, output_path: Path) -> None:
        if not pcm_bytes:
            raise TtsProviderError("CosyVoice 返回空 PCM，不能写入 WAV。")

        if len(pcm_bytes) % 2 != 0:
            raise TtsProviderError(
                f"CosyVoice 返回的 PCM 长度不是 int16 对齐: {len(pcm_bytes)} bytes"
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = output_path.with_suffix(output_path.suffix + ".tmp")

        with wave.open(str(tmp), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(self.config.sample_rate)
            wav.writeframes(pcm_bytes)

        tmp.replace(output_path)
