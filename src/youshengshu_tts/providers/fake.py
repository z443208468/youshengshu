import wave
from pathlib import Path

from .base import TtsProvider, TtsProviderResult


class FakeTtsProvider(TtsProvider):
    def synthesize_to_file(self, text: str, output_path: Path) -> TtsProviderResult:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = output_path.with_suffix(output_path.suffix + ".tmp")

        sample_rate = 22050
        frames = b"\x00\x00" * max(1, min(len(text) * 100, sample_rate))

        with wave.open(str(tmp), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(frames)

        tmp.replace(output_path)
        return TtsProviderResult(
            output_path=str(output_path),
            sample_rate=sample_rate,
        )
