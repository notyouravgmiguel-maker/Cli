"""Analyzer module to inspect and report statistics on a download folder."""

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .hasher import find_duplicates
from .models import ScanSummary
from .rules import Config, format_bytes


def analyze_directory(
    target_dir: Path,
    config: Optional[Config] = None,
    older_than_seconds: Optional[int] = None,
    recursive: bool = False,
) -> ScanSummary:
    """
    Scans target_dir and produces a comprehensive ScanSummary.
    """
    if config is None:
        config = Config()

    summary = ScanSummary(target_dir=target_dir)
    now = datetime.now(timezone.utc).timestamp()

    # Collect files
    files: List[Path] = []
    iterator = target_dir.rglob("*") if recursive else target_dir.iterdir()

    for item in iterator:
        try:
            if not item.is_file() or item.is_symlink():
                continue

            # Ignore hidden files or internal tidy metadata files
            if item.name.startswith(".") or item.name == ".tidy_history.json":
                continue

            stat = item.stat()
            mtime = stat.st_mtime

            if older_than_seconds is not None:
                if (now - mtime) < older_than_seconds:
                    continue

            files.append(item)
            size = stat.st_size
            summary.total_files += 1
            summary.total_bytes += size

            if config.is_temp_file(item):
                summary.temp_files.append(item)
                summary.temp_bytes += size

            cat = config.get_category(item)
            summary.category_counts[cat] = summary.category_counts.get(cat, 0) + 1
            summary.category_bytes[cat] = summary.category_bytes.get(cat, 0) + size

        except (OSError, PermissionError):
            continue

    # Find duplicates
    duplicate_groups = find_duplicates(files)
    summary.duplicate_groups = duplicate_groups

    dup_bytes = 0
    for group in duplicate_groups:
        try:
            # Wasted space = (group_len - 1) * single_file_size
            size = group[0].stat().st_size
            dup_bytes += size * (len(group) - 1)
        except (OSError, PermissionError):
            pass
    summary.duplicate_bytes = dup_bytes

    return summary
