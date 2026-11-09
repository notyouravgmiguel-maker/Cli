# tidy-downloads

A command-line tool built to solve a hyper-specific daily problem: **cleaning up, organizing, deduplicating, and auditing messy download folders**.

## Features

- **Smart Categorization**: Organizes downloads into logical categories (`Documents`, `Images`, `Audio`, `Video`, `Archives`, `Code`, `Installers`, `Books`, `Data`, `Other`).
- **Flexible Sorting Modes**:
  - Sort by category (`tidy organize --by category`)
  - Sort by month/date (`tidy organize --by date`)
  - Sort by category + date (`tidy organize --by category-date`)
- **Safety First**:
  - Full `--dry-run` simulation before touching a single file.
  - Granular conflict resolution (`rename`, `skip`, `overwrite`).
  - Safe transaction-based **Undo** command (`tidy undo`) to revert any operation.
- **Duplicate File Detection**:
  - Fast size pre-filtering and SHA-256 chunked hashing.
  - Identify exact duplicate files (`tidy duplicates`).
  - Automatically deduplicate during organization (`tidy organize --dedupe`).
- **Temporary / Stale Download Cleanup**:
  - Identifies partial / interrupted browser downloads (`.crdownload`, `.part`, `.tmp`).
  - Clean or quarantine them (`tidy organize --clean-tmp`).
- **Age-based Filtering**:
  - Target files older than a specific duration (`--older-than 30d`, `--older-than 2w`).
- **Rich Folder Analysis**:
  - Get actionable insights with `tidy analyze`: category breakdown, size distribution, duplicate wastage, and temp file count.
- **Custom Configuration**:
  - Generate and customize category mappings and rules with `tidy init-config`.

## Installation

```bash
pip install -e .
```

## Quick Start

### 1. Analyze your Downloads folder
```bash
tidy-downloads analyze ~/Downloads
```

### 2. Preview organization (Dry Run)
```bash
tidy-downloads organize ~/Downloads --dry-run
```

### 3. Organize your Downloads
```bash
tidy-downloads organize ~/Downloads
```

### 4. Find duplicates
```bash
tidy-downloads duplicates ~/Downloads
```

### 5. Undo the last organization
```bash
tidy-downloads undo ~/Downloads
```
