from __future__ import annotations

import argparse
from pathlib import Path

from organizer_core import DEFAULT_MODEL, default_folder, run_once, watch


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Recursively organize files and move exact duplicates safely."
    )
    parser.add_argument(
        "--folder",
        type=Path,
        default=None,
        help="Folder or connected external-drive directory to scan. Defaults to Downloads.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Ollama model to use (default: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip Ollama and classify by file extension only.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned moves without changing files.",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Repeat the scan periodically for newly added files.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Seconds between watch scans (default: 60).",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    root = (args.folder or default_folder()).expanduser()
    if args.interval < 1:
        raise SystemExit("--interval must be at least 1 second")

    print(f"Scanning: {root.resolve()}")
    print(f"LLM: {'disabled' if args.no_llm else args.model}")
    print(f"Mode: {'dry run' if args.dry_run else 'move files'}")

    if args.watch:
        try:
            watch(root, args.model, not args.no_llm, args.dry_run, args.interval)
        except KeyboardInterrupt:
            print("Stopped.")
        return

    try:
        stats = run_once(root, args.model, not args.no_llm, args.dry_run)
    except (NotADirectoryError, OSError) as error:
        raise SystemExit(str(error)) from error

    print(
        f"Complete: {stats.scanned} scanned, {stats.categorized} organized, "
        f"{stats.duplicate_groups} duplicate group(s), "
        f"{stats.duplicates_moved} older duplicate(s) moved."
    )
    if stats.errors:
        print(f"Completed with {len(stats.errors)} file error(s).")


if __name__ == "__main__":
    main()
