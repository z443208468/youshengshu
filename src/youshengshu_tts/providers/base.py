from dataclasses import dataclass
from pathlib import Path


@dataclass
class TtsProviderResult:
    output_path: str
    duration_ms: int | None = None
    sample_rate: int | None = None


class TtsProvider:
    def synthesize_to_file(self, text: str, output_path: Path) -> TtsProviderResult:
        raise NotImplementedError
