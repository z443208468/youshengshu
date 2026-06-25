import argparse
import json
import os
import sys
from pathlib import Path

from .config import load_tts_config
from .diagnostics import doctor_payload
from .exceptions import TtsError
from .manifest import load_manifest, manifest_status_payload
from .resume import recover_manifest_state
from .pipeline import (
    TtsPipelineStoppedError,
    create_project,
    find_next_chapter_index,
    get_chapter_or_raise,
    segment_chapter,
    synthesize_chapter,
)
from .providers.base import TtsProvider
from .providers.cosyvoice_http import CosyVoiceHttpProvider
from .providers.fake import FakeTtsProvider


def print_json(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
    sys.stdout.write("\n")
    sys.stdout.flush()


def build_provider(config) -> TtsProvider:
    if os.environ.get("YSS_TTS_FAKE_PROVIDER") == "1":
        return FakeTtsProvider()

    return CosyVoiceHttpProvider(config.cosyvoice)


def cmd_doctor(config_path: str, as_json: bool) -> None:
    config = load_tts_config(config_path)
    payload = doctor_payload(config)
    if as_json:
        print_json(payload)
        if not payload["ok"]:
            sys.exit(1)
        return

    for check in payload["checks"]:
        prefix = "OK" if check["ok"] else check["severity"].upper()
        print(f"[{prefix}] {check['name']}: {check['message']}", file=sys.stderr)
    if not payload["ok"]:
        sys.exit(1)


def cmd_create_project(config_path: str, as_json: bool) -> None:
    config = load_tts_config(config_path)
    manifest = create_project(config)
    payload = {
        "project_id": manifest.project_id,
        "manifest_file": config.paths.manifest_file,
        "chapters": len(manifest.chapters),
    }
    if as_json:
        print_json(payload)
        return
    print(f"Created TTS project: {manifest.project_id}", file=sys.stderr)
    print(f"Chapters: {len(manifest.chapters)}", file=sys.stderr)


def cmd_status(config_path: str, as_json: bool) -> None:
    config = load_tts_config(config_path)
    manifest_path = Path(config.paths.manifest_file)
    if not manifest_path.exists():
        print("[ERROR] TTS manifest 不存在，请先 create-project。", file=sys.stderr)
        sys.exit(1)

    manifest = load_manifest(manifest_path)
    recover_manifest_state(
        config=config,
        manifest=manifest,
        manifest_path=manifest_path,
        retry_failed=False,
        merge_when_complete=True,
    )
    manifest = load_manifest(manifest_path)
    payload = manifest_status_payload(manifest)
    if as_json:
        print_json(payload)
        return

    print(
        f"total={payload['total']} done={payload['done']} pending={payload['pending']}",
        file=sys.stderr,
    )


def cmd_segment(config_path: str, chapter_index: int) -> None:
    config = load_tts_config(config_path)
    manifest_path = Path(config.paths.manifest_file)
    manifest = load_manifest(manifest_path)
    chapter = get_chapter_or_raise(manifest, chapter_index)
    segments = segment_chapter(chapter, config)
    manifest.save(manifest_path)
    print(f"Segmented chapter {chapter_index}: {len(segments)} segments", file=sys.stderr)


def cmd_synthesize(config_path: str, chapter_index: int, as_json: bool) -> None:
    config = load_tts_config(config_path)
    manifest_path = Path(config.paths.manifest_file)
    manifest = load_manifest(manifest_path)
    recover_manifest_state(
        config=config,
        manifest=manifest,
        manifest_path=manifest_path,
        retry_failed=False,
        merge_when_complete=True,
    )
    manifest = load_manifest(manifest_path)
    provider = build_provider(config)

    try:
        synthesize_chapter(chapter_index, config, manifest, manifest_path, provider)
    except TtsPipelineStoppedError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)

    manifest = load_manifest(manifest_path)
    chapter = get_chapter_or_raise(manifest, chapter_index)
    payload = {
        "chapter_index": chapter_index,
        "status": chapter.status,
        "chapter_wav_path": chapter.chapter_wav_path,
    }
    if as_json:
        print_json(payload)
        return
    print(f"Synthesized chapter {chapter_index}", file=sys.stderr)


def cmd_synthesize_next(config_path: str, as_json: bool) -> None:
    config = load_tts_config(config_path)
    manifest_path = Path(config.paths.manifest_file)
    manifest = load_manifest(manifest_path)
    recover_manifest_state(
        config=config,
        manifest=manifest,
        manifest_path=manifest_path,
        retry_failed=False,
        merge_when_complete=True,
    )
    manifest = load_manifest(manifest_path)
    next_index = find_next_chapter_index(manifest)
    if next_index is None:
        payload = {"message": "没有待处理章节", "chapter_index": None}
        if as_json:
            print_json(payload)
            return
        print("没有待处理章节", file=sys.stderr)
        return

    cmd_synthesize(config_path, next_index, as_json)


def cmd_synthesize_all(config_path: str, as_json: bool) -> None:
    config = load_tts_config(config_path)
    manifest_path = Path(config.paths.manifest_file)
    provider = build_provider(config)
    processed: list[int] = []

    while True:
        manifest = load_manifest(manifest_path)
        recover_manifest_state(
            config=config,
            manifest=manifest,
            manifest_path=manifest_path,
            retry_failed=False,
            merge_when_complete=True,
        )
        manifest = load_manifest(manifest_path)
        next_index = find_next_chapter_index(manifest)
        if next_index is None:
            break
        try:
            synthesize_chapter(next_index, config, manifest, manifest_path, provider)
            processed.append(next_index)
        except TtsPipelineStoppedError as exc:
            print(f"[ERROR] {exc}", file=sys.stderr)
            sys.exit(1)

    payload = {"processed_chapters": processed, "count": len(processed)}
    if as_json:
        print_json(payload)
        return
    print(f"Synthesized {len(processed)} chapters", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="youshengshu TTS CLI")
    parser.add_argument("--config", required=True, help="TTS config JSON path")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser("doctor")
    doctor_parser.add_argument("--json", action="store_true")

    create_parser = subparsers.add_parser("create-project")
    create_parser.add_argument("--json", action="store_true")

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--json", action="store_true")

    segment_parser = subparsers.add_parser("segment")
    segment_parser.add_argument("--chapter-index", type=int, required=True)

    synthesize_parser = subparsers.add_parser("synthesize")
    synthesize_parser.add_argument("--chapter-index", type=int, required=True)
    synthesize_parser.add_argument("--json", action="store_true")

    synth_next_parser = subparsers.add_parser("synthesize-next")
    synth_next_parser.add_argument("--json", action="store_true")

    synth_all_parser = subparsers.add_parser("synthesize-all")
    synth_all_parser.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)

    try:
        if args.command == "doctor":
            cmd_doctor(args.config, getattr(args, "json", False))
        elif args.command == "create-project":
            cmd_create_project(args.config, getattr(args, "json", False))
        elif args.command == "status":
            cmd_status(args.config, getattr(args, "json", False))
        elif args.command == "segment":
            cmd_segment(args.config, args.chapter_index)
        elif args.command == "synthesize":
            cmd_synthesize(args.config, args.chapter_index, getattr(args, "json", False))
        elif args.command == "synthesize-next":
            cmd_synthesize_next(args.config, getattr(args, "json", False))
        elif args.command == "synthesize-all":
            cmd_synthesize_all(args.config, getattr(args, "json", False))
        else:
            parser.error(f"未知命令: {args.command}")
    except TtsError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
