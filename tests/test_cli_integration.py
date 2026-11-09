"""Integration and end-to-end tests for tidy-downloads CLI."""

import json
import time
from pathlib import Path
import pytest
from tidy_downloads.cli import main
from tidy_downloads.history import HistoryManager


def test_analyze_empty_directory(tmp_path, capsys):
    ret = main(["analyze", str(tmp_path)])
    assert ret == 0
    captured = capsys.readouterr().out
    assert "Total files found : 0" in captured
    assert "No files found" in captured


def test_organize_dry_run_does_not_modify_files(tmp_path, capsys):
    doc = tmp_path / "notes.txt"
    doc.write_text("my notes", encoding="utf-8")
    img = tmp_path / "pic.png"
    img.write_text("fake image", encoding="utf-8")

    ret = main(["organize", str(tmp_path), "--dry-run"])
    assert ret == 0
    captured = capsys.readouterr().out
    assert "[DRY-RUN]" in captured
    assert "notes.txt" in captured
    assert "pic.png" in captured

    # Ensure files still in root dir and folders not created
    assert doc.exists()
    assert img.exists()
    assert not (tmp_path / "Documents").exists()
    assert not (tmp_path / "Images").exists()


def test_organize_live_and_undo(tmp_path, capsys):
    doc = tmp_path / "report.pdf"
    doc.write_text("important report", encoding="utf-8")
    img = tmp_path / "avatar.png"
    img.write_text("avatar image", encoding="utf-8")

    # 1. Organize
    ret = main(["organize", str(tmp_path)])
    assert ret == 0

    assert not doc.exists()
    assert not img.exists()
    assert (tmp_path / "Documents" / "report.pdf").exists()
    assert (tmp_path / "Images" / "avatar.png").exists()

    # 2. Undo
    ret = main(["undo", str(tmp_path)])
    assert ret == 0

    assert doc.exists()
    assert img.exists()
    # Empty directories should be pruned
    assert not (tmp_path / "Documents").exists()
    assert not (tmp_path / "Images").exists()


def test_organize_with_date_and_category_date(tmp_path):
    f1 = tmp_path / "code.py"
    f1.write_text("print('hi')", encoding="utf-8")

    # Date mode
    ret = main(["organize", str(tmp_path), "--by", "date"])
    assert ret == 0

    # There should now be a YYYY-MM folder containing code.py
    folders = [p for p in tmp_path.iterdir() if p.is_dir() and not p.name.startswith(".")]
    assert len(folders) == 1
    assert (folders[0] / "code.py").exists()

    # Revert
    main(["undo", str(tmp_path)])
    assert f1.exists()

    # Category-date mode
    ret = main(["organize", str(tmp_path), "--by", "category-date"])
    assert ret == 0
    assert (tmp_path / "Code").is_dir()
    subfolders = [p for p in (tmp_path / "Code").iterdir() if p.is_dir()]
    assert len(subfolders) == 1
    assert (subfolders[0] / "code.py").exists()


def test_organize_with_dedupe_and_clean_temp(tmp_path):
    orig = tmp_path / "song.mp3"
    orig.write_text("audio content 123", encoding="utf-8")
    dup = tmp_path / "song_copy.mp3"
    dup.write_text("audio content 123", encoding="utf-8")

    part_file = tmp_path / "large_file.zip.crdownload"
    part_file.write_text("downloading...", encoding="utf-8")

    ret = main(["organize", str(tmp_path), "--dedupe", "--clean-temp"])
    assert ret == 0

    assert (tmp_path / "Audio" / "song.mp3").exists()
    assert (tmp_path / "Duplicates" / "song_copy.mp3").exists()
    assert (tmp_path / "Temporary" / "large_file.zip.crdownload").exists()

    # Undo restores all 3 files
    ret = main(["undo", str(tmp_path)])
    assert ret == 0
    assert orig.exists()
    assert dup.exists()
    assert part_file.exists()


def test_organize_conflict_handling(tmp_path):
    # Setup destination folder already containing a file
    doc_dir = tmp_path / "Documents"
    doc_dir.mkdir()
    (doc_dir / "notes.txt").write_text("existing file", encoding="utf-8")

    new_doc = tmp_path / "notes.txt"
    new_doc.write_text("new notes", encoding="utf-8")

    # Strategy rename: should create notes_1.txt
    ret = main(["organize", str(tmp_path), "--conflict", "rename"])
    assert ret == 0
    assert (doc_dir / "notes.txt").read_text(encoding="utf-8") == "existing file"
    assert (doc_dir / "notes_1.txt").read_text(encoding="utf-8") == "new notes"


def test_duplicates_command_with_isolate(tmp_path, capsys):
    f1 = tmp_path / "file1.txt"
    f2 = tmp_path / "file2.txt"
    f1.write_text("same content", encoding="utf-8")
    f2.write_text("same content", encoding="utf-8")

    # duplicates command with --isolate
    ret = main(["duplicates", str(tmp_path), "--isolate"])
    assert ret == 0
    assert f1.exists()
    assert not f2.exists()
    assert (tmp_path / "Duplicates" / "file2.txt").exists()


def test_init_config(tmp_path):
    target_cfg = tmp_path / "my_config.json"
    ret = main(["init-config", "--output", str(target_cfg)])
    assert ret == 0
    assert target_cfg.exists()
    data = json.loads(target_cfg.read_text(encoding="utf-8"))
    assert "categories" in data
    assert "Documents" in data["categories"]

    # Re-running without --force should fail
    ret = main(["init-config", "--output", str(target_cfg)])
    assert ret == 1

    # Re-running with --force should succeed
    ret = main(["init-config", "--output", str(target_cfg), "--force"])
    assert ret == 0
