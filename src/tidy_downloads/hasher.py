"""File hashing utilities for efficient duplicate file detection."""

import hashlib
from pathlib import Path
from typing import Dict, List, Optional


def compute_file_hash(filepath: Path, chunk_size: int = 65536) -> str:
    """
    Computes SHA-256 hash of a file using chunks to avoid high memory consumption.
    """
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def find_duplicates(files: List[Path]) -> List[List[Path]]:
    """
    Finds exact duplicate files among a list of file paths.
    Uses two-phase detection:
    1. Group files by size (files of different sizes cannot be duplicates).
    2. Group remaining potential duplicates by SHA-256 hash.
    Returns a list of groups (lists of Paths), where each group has 2+ identical files.
    """
    # Phase 1: Group by size
    size_map: Dict[int, List[Path]] = {}
    for p in files:
        try:
            if not p.is_file() or p.is_symlink():
                continue
            size = p.stat().st_size
            size_map.setdefault(size, []).append(p)
        except (OSError, PermissionError):
            continue

    # Filter out single files
    candidates = [flist for flist in size_map.values() if len(flist) > 1]

    # Phase 2: Hash files with identical sizes
    duplicate_groups: List[List[Path]] = []
    for flist in candidates:
        hash_map: Dict[str, List[Path]] = {}
        for p in flist:
            try:
                h = compute_file_hash(p)
                hash_map.setdefault(h, []).append(p)
            except (OSError, PermissionError):
                continue
        for group in hash_map.values():
            if len(group) > 1:
                # Sort group by (mtime, name) deterministically so earliest/alphabetical is first
                group.sort(key=lambda x: (x.stat().st_mtime, str(x)))
                duplicate_groups.append(group)

    return duplicate_groups
