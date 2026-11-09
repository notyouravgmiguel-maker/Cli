"""Organizer module: applies sorting, deduplication, and cleanup rules."""

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .hasher import find_duplicates
from .history import HistoryManager
from .models import ConflictStrategy, FileAction, SortMode
from .rules import Config


def resolve_destination_name(dest: Path, strategy: ConflictStrategy) -> Optional[Path]:
    """
    Handles destination conflicts according to the chosen strategy.
    - SKIP: returns None (skip action)
    - OVERWRITE: returns dest path as is
    - RENAME: appends counter like file_1.ext, file_2.ext
    """
    if not dest.exists():
        return dest

    if strategy == ConflictStrategy.SKIP:
        return None
    elif strategy == ConflictStrategy.OVERWRITE:
        return dest
    elif strategy == ConflictStrategy.RENAME:
        stem = dest.stem
        suffix = dest.suffix
        counter = 1
        while True:
            new_dest = dest.parent / f"{stem}_{counter}{suffix}"
            if not new_dest.exists():
                return new_dest
            counter += 1
    return dest


class Organizer:
    def __init__(
        self,
        target_dir: Path,
        config: Optional[Config] = None,
        sort_mode: SortMode = SortMode.CATEGORY,
        conflict_strategy: ConflictStrategy = ConflictStrategy.RENAME,
        clean_temp: bool = False,
        dedupe: bool = False,
        duplicates_folder: str = "Duplicates",
        temp_folder: str = "Temporary",
        older_than_seconds: Optional[int] = None,
    ):
        self.target_dir = target_dir
        self.config = config or Config()
        self.sort_mode = sort_mode
        self.conflict_strategy = conflict_strategy
        self.clean_temp = clean_temp
        self.dedupe = dedupe
        self.duplicates_folder = duplicates_folder
        self.temp_folder = temp_folder
        self.older_than_seconds = older_than_seconds
        self.history_mgr = HistoryManager(target_dir)

    def compute_destination_folder(self, file_path: Path) -> Path:
        """
        Determines the destination folder for a given file based on sort mode.
        """
        cat = self.config.get_category(file_path)
        mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
        date_folder = mtime.strftime("%Y-%m")

        if self.sort_mode == SortMode.CATEGORY:
            return self.target_dir / cat
        elif self.sort_mode == SortMode.DATE:
            return self.target_dir / date_folder
        elif self.sort_mode == SortMode.CATEGORY_DATE:
            return self.target_dir / cat / date_folder
        return self.target_dir / cat

    def plan_actions(self) -> List[FileAction]:
        """
        Scans target_dir and builds an ordered list of planned actions without modifying disk.
        """
        actions: List[FileAction] = []
        now = datetime.now(timezone.utc).timestamp()

        # Collect top-level files (not already in organized category folders)
        files: List[Path] = []
        for item in self.target_dir.iterdir():
            try:
                if not item.is_file() or item.is_symlink():
                    continue
                if item.name.startswith(".") or item.name == ".tidy_history.json":
                    continue

                if self.older_than_seconds is not None:
                    if (now - item.stat().st_mtime) < self.older_than_seconds:
                        continue

                files.append(item)
            except (OSError, PermissionError):
                continue

        # 1. Identify duplicates if dedupe is enabled
        duplicate_files: Set[Path] = set()
        if self.dedupe:
            dup_groups = find_duplicates(files)
            for group in dup_groups:
                # Keep the first (oldest), mark subsequent files as duplicates
                for dup_file in group[1:]:
                    duplicate_files.add(dup_file)

        # 2. Plan actions for each file
        for f in files:
            size = f.stat().st_size

            # Check if temporary file
            if self.clean_temp and self.config.is_temp_file(f):
                dest_dir = self.target_dir / self.temp_folder
                dest_candidate = dest_dir / f.name
                dest = resolve_destination_name(dest_candidate, self.conflict_strategy)
                if dest:
                    actions.append(
                        FileAction(
                            source=f,
                            destination=dest,
                            action_type="move",
                            size_bytes=size,
                            category="Temporary",
                        )
                    )
                continue

            # Check if marked as duplicate
            if f in duplicate_files:
                dest_dir = self.target_dir / self.duplicates_folder
                dest_candidate = dest_dir / f.name
                dest = resolve_destination_name(dest_candidate, self.conflict_strategy)
                if dest:
                    actions.append(
                        FileAction(
                            source=f,
                            destination=dest,
                            action_type="move",
                            size_bytes=size,
                            category="Duplicates",
                        )
                    )
                continue

            # Normal categorization
            dest_dir = self.compute_destination_folder(f)
            dest_candidate = dest_dir / f.name
            dest = resolve_destination_name(dest_candidate, self.conflict_strategy)
            cat = self.config.get_category(f)

            if dest:
                # If destination is the same as source, skip
                if dest.resolve() == f.resolve():
                    continue
                actions.append(
                    FileAction(
                        source=f,
                        destination=dest,
                        action_type="move",
                        size_bytes=size,
                        category=cat,
                    )
                )

        return actions

    def execute_actions(self, actions: List[FileAction], dry_run: bool = False) -> Tuple[int, List[FileAction]]:
        """
        Executes the planned actions.
        In dry_run mode, no filesystem changes occur.
        Returns (success_count, actions_with_status).
        """
        history_records: List[Dict[str, str]] = []
        success_count = 0

        for action in actions:
            if dry_run:
                action.status = "dry-run"
                success_count += 1
                continue

            try:
                action.destination.parent.mkdir(parents=True, exist_ok=True)
                # If overwriting existing file
                if action.destination.exists() and self.conflict_strategy == ConflictStrategy.OVERWRITE:
                    action.destination.unlink()

                action.source.rename(action.destination)
                action.status = "completed"
                success_count += 1

                history_records.append({
                    "source": str(action.source.resolve()),
                    "destination": str(action.destination.resolve()),
                    "action_type": action.action_type,
                    "category": action.category,
                })
            except OSError as e:
                action.status = "failed"
                action.error_message = str(e)

        if not dry_run and history_records:
            self.history_mgr.record_operation(history_records)

        return success_count, actions
