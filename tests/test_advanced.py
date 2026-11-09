"""Additional edge-case and failure mode tests."""

import pytest
from pathlib import Path
from tidy_downloads.cli import main
from tidy_downloads.history import HistoryManager
from tidy_downloads.organizer import Organizer, resolve_destination_name
from tidy_downloads.models import ConflictStrategy, SortMode
from tidy_downloads.rules import Config


def test_conflict_strategy_overwrite_and_skip(tmp_path):
    target = tmp_path / "file.txt"
    target.write_text("orig", encoding="utf-8")

    # Skip returns None
    assert resolve_destination_name(target, ConflictStrategy.SKIP) is None

    # Overwrite returns the same path
    assert resolve_destination_name(target, ConflictStrategy.OVERWRITE) == target

    # Rename returns file_1.txt
    res = resolve_destination_name(target, ConflictStrategy.RENAME)
    assert res == tmp_path / "file_1.txt"

    # If file_1.txt already exists, should return file_2.txt
    (tmp_path / "file_1.txt").write_text("another", encoding="utf-8")
    assert resolve_destination_name(target, ConflictStrategy.RENAME) == tmp_path / "file_2.txt"


def test_organize_with_skip_and_overwrite(tmp_path):
    # Setup
    doc_dir = tmp_path / "Documents"
    doc_dir.mkdir()
    existing = doc_dir / "doc.pdf"
    existing.write_text("old content", encoding="utf-8")

    src = tmp_path / "doc.pdf"
    src.write_text("new content", encoding="utf-8")

    # 1. Skip strategy: does not move
    ret = main(["organize", str(tmp_path), "--conflict", "skip"])
    assert ret == 0
    assert src.exists()
    assert existing.read_text(encoding="utf-8") == "old content"

    # 2. Overwrite strategy: replaces destination
    ret = main(["organize", str(tmp_path), "--conflict", "overwrite"])
    assert ret == 0
    assert not src.exists()
    assert existing.read_text(encoding="utf-8") == "new content"


def test_undo_when_no_history(tmp_path, capsys):
    ret = main(["undo", str(tmp_path)])
    assert ret == 0
    captured = capsys.readouterr().out
    assert "No tidy operations found" in captured


def test_undo_when_file_deleted_externally(tmp_path):
    f = tmp_path / "music.mp3"
    f.write_text("audio", encoding="utf-8")

    # Organize
    main(["organize", str(tmp_path)])
    dest = tmp_path / "Audio" / "music.mp3"
    assert dest.exists()

    # Manually delete dest before undo
    dest.unlink()

    # Undo should handle missing file gracefully with error report
    ret = main(["undo", str(tmp_path)])
    assert ret == 1
    assert not f.exists()


def test_cli_nonexistent_directory(capsys):
    ret = main(["analyze", "/nonexistent/folder/path/xyz"])
    assert ret == 1
    err = capsys.readouterr().err
    assert "Directory does not exist" in err

    ret = main(["organize", "/nonexistent/folder/path/xyz"])
    assert ret == 1

    ret = main(["duplicates", "/nonexistent/folder/path/xyz"])
    assert ret == 1

    ret = main(["undo", "/nonexistent/folder/path/xyz"])
    assert ret == 1


def test_analyze_with_subdirectories_recursive(tmp_path, capsys):
    sub = tmp_path / "subfolder"
    sub.mkdir()
    (sub / "nested.jpg").write_text("img", encoding="utf-8")
    (tmp_path / "root.jpg").write_text("img", encoding="utf-8")

    # Non-recursive should only see root.jpg
    main(["analyze", str(tmp_path)])
    out = capsys.readouterr().out
    assert "Total files found : 1" in out

    # Recursive should see both
    main(["analyze", str(tmp_path), "-r"])
    out = capsys.readouterr().out
    assert "Total files found : 2" in out
