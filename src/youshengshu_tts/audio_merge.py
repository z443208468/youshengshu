import wave
from pathlib import Path


def merge_wav_files(input_paths: list[Path], output_path: Path) -> None:
    if not input_paths:
        raise ValueError("没有可合并的 wav 文件")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_path.with_suffix(output_path.suffix + ".tmp")

    with wave.open(str(input_paths[0]), "rb") as first:
        params = first.getparams()

    with wave.open(str(tmp), "wb") as out:
        out.setparams(params)
        for path in input_paths:
            with wave.open(str(path), "rb") as src:
                if src.getparams()[:3] != params[:3]:
                    raise ValueError(f"wav 参数不一致: {path}")
                out.writeframes(src.readframes(src.getnframes()))

    tmp.replace(output_path)
