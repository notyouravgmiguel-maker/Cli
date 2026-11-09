"""Core data models and structures for tidy-downloads."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional


class ConflictStrategy(str, Enum):
    RENAME = "rename"
    SKIP = "skip"
    OVERWRITE = "overwrite"


class SortMode(str, Enum):
    CATEGORY = "category"
    DATE = "date"
    CATEGORY_DATE = "category-date"


@dataclass
class FileAction:
    source: Path
    destination: Path
    action_type: str  # 'move', 'delete', 'duplicate_archive'
    size_bytes: int
    category: str
    status: str = "pending"  # 'pending', 'completed', 'skipped', 'failed'
    error_message: Optional[str] = None


@dataclass
class ScanSummary:
    target_dir: Path
    total_files: int = 0
    total_bytes: int = 0
    category_counts: Dict[str, int] = field(default_factory=dict)
    category_bytes: Dict[str, int] = field(default_factory=dict)
    duplicate_groups: List[List[Path]] = field(default_factory=list)
    duplicate_bytes: int = 0
    temp_files: List[Path] = field(default_factory=list)
    temp_bytes: int = 0


@dataclass
class HistoryEntry:
    timestamp: str
    operation_id: str
    actions: List[Dict[str, str]] = field(default_factory=list)
