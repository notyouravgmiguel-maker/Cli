"""Command-Line Interface for tidy-downloads."""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from .analyzer import analyze_directory
from .history import HistoryManager
from .models import ConflictStrategy, SortMode
from .organizer import Organizer
from .rules import Config, format_bytes, parse_duration_to_seconds


def handle_analyze(args: argparse.Namespace) -> int:
    target_dir = Path(args.path).resolve()
    if not target_dir.is_dir():
        print(f"Error: Directory does not exist: {target_dir}", file=sys.stderr)
        return 1

    config = Config.from_file(Path(args.config)) if args.config else Config()
    older_seconds = parse_duration_to_seconds(args.older_than) if args.older_than else None

    print(f"\n📂 Analyzing directory: {target_dir}")
    if args.older_than:
        print(f"⏳ Filter: files older than {args.older_than}")
    print("-" * 55)

    summary = analyze_directory(
        target_dir=target_dir,
        config=config,
        older_than_seconds=older_seconds,
        recursive=args.recursive,
    )

    print(f"Total files found : {summary.total_files:,}")
    print(f"Total disk usage  : {format_bytes(summary.total_bytes)}")
    print("\n📊 Breakdown by Category:")
    if not summary.category_counts:
        print("  (No files found)")
    else:
        for cat in sorted(summary.category_counts.keys()):
            count = summary.category_counts[cat]
            size = summary.category_bytes.get(cat, 0)
            print(f"  • {cat:<14}: {count:>5} files  ({format_bytes(size)})")

    print("\n🔍 Temporary / Partial Downloads:")
    if summary.temp_files:
        print(f"  Found {len(summary.temp_files)} temp file(s) consuming {format_bytes(summary.temp_bytes)}:")
        for tf in summary.temp_files[:5]:
            print(f"    - {tf.name}")
        if len(summary.temp_files) > 5:
            print(f"    ... and {len(summary.temp_files) - 5} more.")
    else:
        print("  None found.")

    print("\n👥 Duplicate Files:")
    if summary.duplicate_groups:
        print(f"  Found {len(summary.duplicate_groups)} duplicate group(s), wasting {format_bytes(summary.duplicate_bytes)}:")
        for i, group in enumerate(summary.duplicate_groups[:3], 1):
            print(f"    Group {i} ({format_bytes(group[0].stat().st_size)} each):")
            for item in group:
                print(f"      - {item.name}")
        if len(summary.duplicate_groups) > 3:
            print(f"    ... and {len(summary.duplicate_groups) - 3} more duplicate groups.")
    else:
        print("  No duplicates detected.")

    print("-" * 55)
    return 0


def handle_organize(args: argparse.Namespace) -> int:
    target_dir = Path(args.path).resolve()
    if not target_dir.is_dir():
        print(f"Error: Directory does not exist: {target_dir}", file=sys.stderr)
        return 1

    config = Config.from_file(Path(args.config)) if args.config else Config()
    older_seconds = parse_duration_to_seconds(args.older_than) if args.older_than else None
    sort_mode = SortMode(args.by)
    conflict = ConflictStrategy(args.conflict)

    organizer = Organizer(
        target_dir=target_dir,
        config=config,
        sort_mode=sort_mode,
        conflict_strategy=conflict,
        clean_temp=args.clean_temp,
        dedupe=args.dedupe,
        duplicates_folder=args.duplicates_folder,
        temp_folder=args.temp_folder,
        older_than_seconds=older_seconds,
    )

    actions = organizer.plan_actions()

    prefix = "[DRY-RUN] " if args.dry_run else ""
    print(f"\n{prefix}Planning organization for: {target_dir}")
    print(f"Mode: Sort by {sort_mode.value} | Conflict: {conflict.value}")
    if args.dedupe:
        print("Deduplication: Enabled (duplicate copies will move to Duplicates/)")
    if args.clean_temp:
        print("Clean Temporary: Enabled (partial downloads will move to Temporary/)")
    print("-" * 55)

    if not actions:
        print("No files eligible for organization.")
        return 0

    print(f"Found {len(actions)} file(s) to organize:\n")
    for act in actions:
        rel_dest = act.destination.relative_to(target_dir)
        print(f"  {act.source.name} ➔ {rel_dest}  [{act.category}] ({format_bytes(act.size_bytes)})")

    print("-" * 55)

    success_count, results = organizer.execute_actions(actions, dry_run=args.dry_run)
    if args.dry_run:
        print(f"Dry run complete. {success_count} file(s) would be organized.")
        print("Run without '--dry-run' to execute.")
    else:
        print(f"Successfully organized {success_count} file(s)!")
        failed = [a for a in results if a.status == "failed"]
        if failed:
            print(f"Warning: {len(failed)} action(s) failed:")
            for f in failed:
                print(f"  - {f.source.name}: {f.error_message}")

    return 0


def handle_duplicates(args: argparse.Namespace) -> int:
    target_dir = Path(args.path).resolve()
    if not target_dir.is_dir():
        print(f"Error: Directory does not exist: {target_dir}", file=sys.stderr)
        return 1

    from .hasher import find_duplicates

    files = [p for p in target_dir.iterdir() if p.is_file() and not p.name.startswith(".")]
    groups = find_duplicates(files)

    print(f"\n🔍 Duplicate Search: {target_dir}")
    print("-" * 55)
    if not groups:
        print("No duplicate files found.")
        return 0

    total_wasted = 0
    for i, group in enumerate(groups, 1):
        size = group[0].stat().st_size
        wasted = size * (len(group) - 1)
        total_wasted += wasted
        print(f"\nGroup {i}: {len(group)} copies ({format_bytes(size)} each, {format_bytes(wasted)} wasted)")
        print(f"  Original:  {group[0].name}")
        for dup in group[1:]:
            print(f"  Duplicate: {dup.name}")

    print("-" * 55)
    print(f"Total wasted space across {len(groups)} group(s): {format_bytes(total_wasted)}")

    if args.isolate:
        dup_dir = target_dir / "Duplicates"
        dup_dir.mkdir(parents=True, exist_ok=True)
        moved = 0
        for group in groups:
            for dup in group[1:]:
                target = dup_dir / dup.name
                # handle collision
                counter = 1
                while target.exists():
                    target = dup_dir / f"{dup.stem}_{counter}{dup.suffix}"
                    counter += 1
                dup.rename(target)
                moved += 1
        print(f"Moved {moved} duplicate file(s) to {dup_dir.name}/")

    return 0


def handle_undo(args: argparse.Namespace) -> int:
    target_dir = Path(args.path).resolve()
    if not target_dir.is_dir():
        print(f"Error: Directory does not exist: {target_dir}", file=sys.stderr)
        return 1

    history_mgr = HistoryManager(target_dir)
    last_op = history_mgr.get_last_operation()

    if not last_op:
        print(f"No tidy operations found to undo in {target_dir}.")
        return 0

    print(f"\n⏪ Reverting operation '{last_op['id']}' from {last_op['timestamp']}...")
    reverted, errors = history_mgr.undo_last_operation()

    print(f"Reverted {reverted} file(s) back to their original locations.")
    if errors:
        print("Errors encountered during undo:")
        for err in errors:
            print(f"  - {err}")

    return 0 if not errors else 1


def handle_init_config(args: argparse.Namespace) -> int:
    output_path = Path(args.output).resolve()
    if output_path.exists() and not args.force:
        print(f"Error: Configuration file '{output_path}' already exists. Use --force to overwrite.", file=sys.stderr)
        return 1

    config = Config()
    output_path.write_text(config.to_json(), encoding="utf-8")
    print(f"Created default configuration file at: {output_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tidy-downloads",
        description="A CLI tool to clean, categorize, deduplicate, and tidy download folders.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # organize
    org_parser = subparsers.add_parser("organize", help="Organize files in the target directory.")
    org_parser.add_argument("path", nargs="?", default=".", help="Target directory (default: current dir).")
    org_parser.add_argument(
        "--by",
        choices=["category", "date", "category-date"],
        default="category",
        help="Organization hierarchy (default: category).",
    )
    org_parser.add_argument(
        "--conflict",
        choices=["rename", "skip", "overwrite"],
        default="rename",
        help="Conflict strategy if file already exists in destination (default: rename).",
    )
    org_parser.add_argument("--dry-run", action="store_true", help="Preview changes without moving files.")
    org_parser.add_argument("--dedupe", action="store_true", help="Move duplicate files into Duplicates folder.")
    org_parser.add_argument("--clean-temp", action="store_true", help="Move partial/temp files to Temporary folder.")
    org_parser.add_argument("--older-than", help="Only organize files older than duration (e.g., 30d, 12h, 2w).")
    org_parser.add_argument("--config", help="Path to custom JSON configuration file.")
    org_parser.add_argument("--duplicates-folder", default="Duplicates", help="Folder name for duplicates.")
    org_parser.add_argument("--temp-folder", default="Temporary", help="Folder name for temporary files.")
    org_parser.set_defaults(func=handle_organize)

    # analyze
    ana_parser = subparsers.add_parser("analyze", help="Analyze target directory and display statistics.")
    ana_parser.add_argument("path", nargs="?", default=".", help="Target directory (default: current dir).")
    ana_parser.add_argument("--recursive", "-r", action="store_true", help="Include subdirectories in analysis.")
    ana_parser.add_argument("--older-than", help="Filter files older than duration (e.g., 30d, 12h, 2w).")
    ana_parser.add_argument("--config", help="Path to custom JSON configuration file.")
    ana_parser.set_defaults(func=handle_analyze)

    # duplicates
    dup_parser = subparsers.add_parser("duplicates", help="Find duplicate files by content hashing.")
    dup_parser.add_argument("path", nargs="?", default=".", help="Target directory (default: current dir).")
    dup_parser.add_argument("--isolate", action="store_true", help="Move duplicates into a Duplicates folder.")
    dup_parser.set_defaults(func=handle_duplicates)

    # undo
    undo_parser = subparsers.add_parser("undo", help="Revert the last tidy organization operation.")
    undo_parser.add_argument("path", nargs="?", default=".", help="Target directory (default: current dir).")
    undo_parser.set_defaults(func=handle_undo)

    # init-config
    init_parser = subparsers.add_parser("init-config", help="Generate a default JSON configuration file.")
    init_parser.add_argument("--output", "-o", default="tidy-config.json", help="Output file path (default: tidy-config.json).")
    init_parser.add_argument("--force", "-f", action="store_true", help="Overwrite existing configuration file.")
    init_parser.set_defaults(func=handle_init_config)

    return parser


def main(args: Optional[List[str]] = None) -> int:
    parser = build_parser()
    parsed_args = parser.parse_args(args)
    return parsed_args.func(parsed_args)
