import json
import sys
from pathlib import Path

from .config import load_config
from .chapter_splitter import split_chapters, write_chapters
from .exceptions import YoushengshuError
from .lmstudio_client import LMStudioClient
from .progress import TranslationManifest
from .translator import run_translation_pipeline


def _build_status_json(manifest: TranslationManifest) -> dict:
    summary = manifest.get_summary()
    chapters = [ch.to_dict() for ch in manifest.chapters]
    return {
        "total": summary["total"],
        "done": summary["done"],
        "pending": summary["pending"],
        "failed": summary["failed"],
        "in_progress": summary["in_progress"],
        "next_chapter": summary["next_chapter"],
        "failed_list": [
            {"index": idx, "en_path": ep, "error": err}
            for idx, ep, err in summary["failed_list"]
        ],
        "chapters": chapters,
    }


def cmd_split(config_path: str, as_json: bool = False) -> None:
    config = load_config(config_path)

    input_path = Path(config.paths.input_file)
    if not input_path.exists():
        print(f"[ERROR] 输入文件不存在: {input_path}")
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        source_text = f.read()

    chapters = split_chapters(
        source_text,
        min_valid_chapter_chars=config.chapter_split.min_valid_chapter_chars,
        strict_sequence=config.chapter_split.strict_chapter_sequence,
    )

    en_dir = Path(config.paths.en_chapters_dir)
    records = write_chapters(chapters, en_dir)

    manifest = TranslationManifest.create_from_records(
        source_file=str(input_path),
        records=records,
    )

    manifest_path = Path(config.paths.manifest_file)
    manifest.save(manifest_path)

    if as_json:
        payload = {
            "source": str(input_path),
            "chapters": len(chapters),
            "en_chapters_dir": str(en_dir),
            "manifest_file": str(manifest_path),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print("Split completed.")
    print(f"Source: {input_path}")
    print(f"Chapters: {len(chapters)}")
    print(f"Output: {en_dir}")
    print(f"Manifest: {manifest_path}")


def cmd_translate(config_path: str, max_chapters: int = 0) -> None:
    config = load_config(config_path)

    manifest_path = Path(config.paths.manifest_file)
    if not manifest_path.exists():
        print(
            "[ERROR] Manifest 文件不存在。请先运行 split 命令。"
        )
        sys.exit(1)

    manifest = TranslationManifest.load(manifest_path)

    # Check for stale chapters
    reset_indices = manifest.check_and_reset_stale()
    if reset_indices:
        print(f"检测到 {len(reset_indices)} 章节的源文件已变更，状态已重置。")

    client = LMStudioClient(config.lmstudio)
    try:
        model_id = client.resolve_model_id()
        print(f"Using LM Studio model: {model_id}")
    except YoushengshuError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    results = run_translation_pipeline(config, client, manifest, max_chapters=max_chapters)

    if not results:
        summary = manifest.get_summary()
        print(f"\nTotal chapters: {summary['total']}")
        print(f"Done: {summary['done']}")
        print(f"Pending: {summary['pending']}")
        print(f"Failed: {summary['failed']}")
        print(f"In progress: {summary['in_progress']}")
        return

    print(f"\n翻译完成: {len(results)} 章")


def cmd_status(config_path: str, as_json: bool = False) -> None:
    config = load_config(config_path)

    manifest_path = Path(config.paths.manifest_file)
    if not manifest_path.exists():
        if as_json:
            print(json.dumps({"error": "Manifest 文件不存在。请先运行 split 命令。"}, ensure_ascii=False))
        else:
            print(
                "[ERROR] Manifest 文件不存在。请先运行 split 命令。"
            )
        sys.exit(1)

    manifest = TranslationManifest.load(manifest_path)

    if as_json:
        payload = _build_status_json(manifest)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    summary = manifest.get_summary()

    print(f"Total chapters: {summary['total']}")
    print(f"Done: {summary['done']}")
    print(f"Pending: {summary['pending']}")
    print(f"Failed: {summary['failed']}")
    print(f"In progress: {summary['in_progress']}")
    print(f"Next chapter: {summary['next_chapter'] or 'None (all done)'}")

    if summary["failed_list"]:
        print("\nFailed chapters:")
        for idx, en_path, error in summary["failed_list"]:
            print(f"  - chapter_{idx:03d}_en.txt: {error}")


def cmd_all(config_path: str) -> None:
    cmd_split(config_path)
    cmd_translate(config_path)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="小说 TXT 分章节 + LM Studio 批量翻译工具"
    )
    parser.add_argument(
        "--config",
        default="config/default_config.json",
        help="配置文件路径 (默认: config/default_config.json)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    split_parser = subparsers.add_parser("split", help="按章节切分 TXT 文件")
    split_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="以 JSON 格式输出结果",
    )

    translate_parser = subparsers.add_parser("translate", help="批量翻译（支持续跑）")
    translate_parser.add_argument(
        "--max-chapters",
        type=int,
        default=0,
        help="最大翻译章节数 (0 表示全部)",
    )

    status_parser = subparsers.add_parser("status", help="查看当前翻译进度")
    status_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="以 JSON 格式输出结果",
    )

    subparsers.add_parser("all", help="执行 split + translate")

    args = parser.parse_args()

    try:
        if args.command == "split":
            cmd_split(args.config, as_json=getattr(args, "json_output", False))
        elif args.command == "translate":
            cmd_translate(args.config, max_chapters=getattr(args, "max_chapters", 0))
        elif args.command == "status":
            cmd_status(args.config, as_json=getattr(args, "json_output", False))
        elif args.command == "all":
            cmd_all(args.config)
    except YoushengshuError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[UNEXPECTED ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
