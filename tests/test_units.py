"""Unit tests for rules, hasher, duration parsing, and models."""

import pytest
from pathlib import Path
from tidy_downloads.rules import (
    Config,
    format_bytes,
    parse_duration_to_seconds,
    DEFAULT_CATEGORIES,
)
from tidy_downloads.hasher import compute_file_hash, find_duplicates
from tidy_downloads.models import ConflictStrategy, SortMode


def test_parse_duration_to_seconds():
    assert parse_duration_to_seconds("30s") == 30
    assert parse_duration_to_seconds("15m") == 15 * 60
    assert parse_duration_to_seconds("2h") == 2 * 3600
    assert parse_duration_to_seconds("5d") == 5 * 86400
    assert parse_duration_to_seconds("2w") == 2 * 7 * 86400
    # default unit is days
    assert parse_duration_to_seconds("7") == 7 * 86400

    with pytest.raises(ValueError):
        parse_duration_to_seconds("invalid")
    with pytest.raises(ValueError):
        parse_duration_to_seconds("10x")


def test_format_bytes():
    assert format_bytes(500) == "500.0 B"
    assert format_bytes(1024) == "1.0 KB"
    assert format_bytes(1024 * 1024 * 5) == "5.0 MB"
    assert format_bytes(1024 * 1024 * 1024 * 2) == "2.0 GB"


def test_config_category_mapping(tmp_path):
    config = Config()
    assert config.get_category(Path("document.pdf")) == "Documents"
    assert config.get_category(Path("photo.JPG")) == "Images"
    assert config.get_category(Path("archive.tar.gz")) == "Archives"
    assert config.get_category(Path("app.py")) == "Code"
    assert config.get_category(Path("song.mp3")) == "Audio"
    assert config.get_category(Path("movie.mkv")) == "Video"
    assert config.get_category(Path("setup.exe")) == "Installers"
    assert config.get_category(Path("novel.epub")) == "Books"
    assert config.get_category(Path("unknown.xyz")) == "Other"

    # Temporary files
    assert config.is_temp_file(Path("file.crdownload")) is True
    assert config.is_temp_file(Path("file.part")) is True
    assert config.is_temp_file(Path("file.tmp")) is True
    assert config.is_temp_file(Path("file.pdf")) is False


def test_custom_config_json(tmp_path):
    custom_cfg_file = tmp_path / "custom.json"
    custom_cfg_file.write_text(
        '{"categories": {"CustomCat": [".foo", ".bar"]}, "temp_extensions": [".mytmp"]}',
        encoding="utf-8"
    )
    cfg = Config.from_file(custom_cfg_file)
    assert cfg.get_category(Path("test.foo")) == "CustomCat"
    assert cfg.get_category(Path("test.bar")) == "CustomCat"
    assert cfg.is_temp_file(Path("test.mytmp")) is True
    assert cfg.get_category(Path("test.pdf")) == "Other"


def test_hasher_and_duplicates(tmp_path):
    f1 = tmp_path / "file1.txt"
    f2 = tmp_path / "file2.txt"
    f3 = tmp_path / "file3.txt"

    f1.write_text("Hello world", encoding="utf-8")
    f2.write_text("Hello world", encoding="utf-8")
    f3.write_text("Different content", encoding="utf-8")

    assert compute_file_hash(f1) == compute_file_hash(f2)
    assert compute_file_hash(f1) != compute_file_hash(f3)

    groups = find_duplicates([f1, f2, f3])
    assert len(groups) == 1
    assert len(groups[0]) == 2
    assert {p.name for p in groups[0]} == {"file1.txt", "file2.txt"}
