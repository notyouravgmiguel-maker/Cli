"""Rules and configuration for categorizing files and parsing CLI parameters."""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set

DEFAULT_CATEGORIES: Dict[str, List[str]] = {
    "Documents": [
        ".pdf", ".doc", ".docx", ".odt", ".rtf", ".txt", ".tex", ".wpd", ".pages"
    ],
    "Spreadsheets": [
        ".xls", ".xlsx", ".csv", ".tsv", ".ods", ".numbers"
    ],
    "Presentations": [
        ".ppt", ".pptx", ".key", ".odp"
    ],
    "Images": [
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".tiff", ".ico", ".raw", ".heic"
    ],
    "Audio": [
        ".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a", ".wma"
    ],
    "Video": [
        ".mp4", ".mkv", ".mov", ".avi", ".flv", ".wmv", ".webm", ".m4v"
    ],
    "Archives": [
        ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar", ".xz", ".tgz", ".iso"
    ],
    "Code": [
        ".py", ".js", ".ts", ".html", ".css", ".json", ".xml", ".yaml", ".yml",
        ".java", ".c", ".cpp", ".h", ".hpp", ".go", ".rs", ".rb", ".php", ".sh",
        ".sql", ".md"
    ],
    "Installers": [
        ".deb", ".rpm", ".dmg", ".pkg", ".exe", ".msi", ".apk", ".AppImage"
    ],
    "Books": [
        ".epub", ".mobi", ".azw", ".azw3", ".djvu"
    ],
    "Data": [
        ".sqlite", ".db", ".parquet", ".arrow", ".feather", ".hdf5", ".sqlitedb"
    ]
}

TEMP_EXTENSIONS: Set[str] = {
    ".crdownload", ".part", ".tmp", ".download", ".partial"
}


class Config:
    def __init__(self, categories: Optional[Dict[str, List[str]]] = None, temp_exts: Optional[Set[str]] = None):
        self.categories: Dict[str, List[str]] = categories or DEFAULT_CATEGORIES
        self.temp_extensions: Set[str] = temp_exts or TEMP_EXTENSIONS
        # Build inverted lookup for speed
        self._ext_to_cat: Dict[str, str] = {}
        for cat, exts in self.categories.items():
            for ext in exts:
                self._ext_to_cat[ext.lower()] = cat

    def get_category(self, filepath: Path) -> str:
        """Determines category for a given file path based on its extension."""
        ext = filepath.suffix.lower()
        # Handle compound extensions like .tar.gz if present
        if len(filepath.suffixes) > 1:
            compound = "".join(filepath.suffixes[-2:]).lower()
            if compound in self._ext_to_cat:
                return self._ext_to_cat[compound]

        return self._ext_to_cat.get(ext, "Other")

    def is_temp_file(self, filepath: Path) -> bool:
        """Checks if a file is an incomplete or temporary download file."""
        ext = filepath.suffix.lower()
        return ext in self.temp_extensions

    def to_json(self) -> str:
        return json.dumps({
            "categories": self.categories,
            "temp_extensions": list(self.temp_extensions)
        }, indent=2)

    @classmethod
    def from_file(cls, path: Path) -> "Config":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(
            categories=data.get("categories"),
            temp_exts=set(data.get("temp_extensions", []))
        )


def parse_duration_to_seconds(duration_str: str) -> int:
    """
    Parses a string like '30d', '12h', '45m', '2w' into seconds.
    Supports units: s (seconds), m (minutes), h (hours), d (days), w (weeks).
    """
    pattern = r"^(\d+)\s*([smhdw]?)$"
    match = re.match(pattern, duration_str.strip().lower())
    if not match:
        raise ValueError(
            f"Invalid duration format: '{duration_str}'. Use format like '30d', '12h', '45m', '2w'."
        )
    value, unit = match.groups()
    val = int(value)
    multipliers = {
        "": 86400,  # Default unit is days
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400,
        "w": 604800,
    }
    return val * multipliers[unit]


def format_bytes(size: int) -> str:
    """Format bytes into human readable string (KB, MB, GB, etc.)."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(size) < 1024.0:
            return f"{size:3.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"
