"""Base fixtures are read-only: their hashes are pinned in fixtures/MANIFEST.sha256."""

import hashlib
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_manifest_matches_files() -> None:
    lines = (FIXTURES / "MANIFEST.sha256").read_text().splitlines()
    assert lines
    for line in lines:
        digest, _, name = line.partition("  ")
        assert hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() == digest, name


def test_basic_set_and_measurements_present() -> None:
    assert (FIXTURES / "patterns/base/Aldrich-Womens-6th-Ed-Basic-Blocks.sm2d").is_file()
    assert (FIXTURES / "measurements/Aldrich-Womens-MultiSize-06-14.smms").is_file()


def test_pattern_points_at_shipped_measurement_file() -> None:
    text = (FIXTURES / "patterns/base/Aldrich-Womens-6th-Ed-Basic-Blocks.sm2d").read_text()
    assert "<measurements>Aldrich-Womens-MultiSize-06-14.smms</measurements>" in text
