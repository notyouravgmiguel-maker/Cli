"""History and Undo management for tidy-downloads operations."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

HISTORY_FILENAME = ".tidy_history.json"


class HistoryManager:
    def __init__(self, target_dir: Path):
        self.target_dir = target_dir
        self.history_file = target_dir / HISTORY_FILENAME

    def _load(self) -> List[Dict]:
        if not self.history_file.exists():
            return []
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []

    def _save(self, history: List[Dict]) -> None:
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2)
        except OSError:
            pass

    def record_operation(self, actions: List[Dict[str, str]]) -> str:
        """
        Records completed actions in the history log.
        Returns the operation_id.
        """
        history = self._load()
        op_id = str(uuid.uuid4())[:8]
        entry = {
            "id": op_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actions": actions,
        }
        history.append(entry)
        self._save(history)
        return op_id

    def get_last_operation(self) -> Optional[Dict]:
        history = self._load()
        return history[-1] if history else None

    def undo_last_operation(self) -> Tuple[int, List[str]]:
        """
        Reverts the most recent operation recorded in history.
        Restores files back to their original paths.
        Cleans up newly empty folders created by the operation.
        Returns (reverted_count, errors_list).
        """
        history = self._load()
        if not history:
            return 0, ["No operations to undo."]

        last_op = history.pop()
        actions = last_op.get("actions", [])
        reverted_count = 0
        errors: List[str] = []

        # Undo in reverse order of actions
        for act in reversed(actions):
            src_str = act.get("source")
            dst_str = act.get("destination")
            act_type = act.get("action_type")

            if not src_str or not dst_str:
                continue

            src = Path(src_str)
            dst = Path(dst_str)

            if act_type == "move":
                if not dst.exists():
                    errors.append(f"Cannot revert '{dst.name}': destination file no longer exists.")
                    continue
                try:
                    src.parent.mkdir(parents=True, exist_ok=True)
                    dst.rename(src)
                    reverted_count += 1

                    # If dst parent is empty, prune it up to target_dir
                    parent = dst.parent
                    while parent != self.target_dir and parent.exists():
                        try:
                            if not any(parent.iterdir()):
                                parent.rmdir()
                                parent = parent.parent
                            else:
                                break
                        except OSError:
                            break

                except OSError as e:
                    errors.append(f"Failed to move '{dst}' back to '{src}': {e}")

        # Update history file
        self._save(history)
        # Remove history file if no history remains
        if not history and self.history_file.exists():
            try:
                self.history_file.unlink()
            except OSError:
                pass

        return reverted_count, errors
