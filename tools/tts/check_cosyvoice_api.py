import argparse
import wave
from pathlib import Path

import requests


def write_pcm_as_wav(pcm: bytes, path: Path, sample_rate: int = 22050) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:50000")
    parser.add_argument("--mode", default="sft", choices=["sft", "zero_shot", "cross_lingual", "instruct"])
    parser.add_argument("--text", default="这是有声书工坊的本地语音合成测试。")
    parser.add_argument("--spk-id", default="中文女")
    parser.add_argument("--prompt-text", default="")
    parser.add_argument("--prompt-wav", default="")
    parser.add_argument("--instruct-text", default="用自然、稳定的有声书旁白语气朗读。")
    parser.add_argument("--out", default="data/audio_projects/smoke/cosyvoice_smoke.wav")
    args = parser.parse_args()

    url = f"{args.base_url.rstrip('/')}/inference_{args.mode}"
    data = {"tts_text": args.text}
    files = None
    opened = None

    try:
        if args.mode == "sft":
            data["spk_id"] = args.spk_id
        elif args.mode == "zero_shot":
            data["prompt_text"] = args.prompt_text
            opened = open(args.prompt_wav, "rb")
            files = {"prompt_wav": ("prompt_wav", opened, "application/octet-stream")}
        elif args.mode == "cross_lingual":
            opened = open(args.prompt_wav, "rb")
            files = {"prompt_wav": ("prompt_wav", opened, "application/octet-stream")}
        elif args.mode == "instruct":
            data["spk_id"] = args.spk_id
            data["instruct_text"] = args.instruct_text

        response = requests.post(url, data=data, files=files, stream=True, timeout=120)
        response.raise_for_status()
        pcm = b"".join(response.iter_content(chunk_size=16000))
        if not pcm:
            raise RuntimeError("empty audio")
        if len(pcm) % 2 != 0:
            raise RuntimeError(f"PCM not int16 aligned: {len(pcm)} bytes")

        write_pcm_as_wav(pcm, Path(args.out))
        print(f"[OK] wrote {args.out}")
        return 0
    finally:
        if opened:
            opened.close()


if __name__ == "__main__":
    raise SystemExit(main())
