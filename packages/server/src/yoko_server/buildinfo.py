"""Build and fixture metadata shown by /api/build."""

from __future__ import annotations

import hashlib
import os
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any

# See docs/adr/0002-seamly2d-version-and-file-formats.md. Moved only deliberately.
SEAMLY2D_PIN = "v2026.10.5.154"
PATTERN_FORMATS_READ = ("0.6.8", "0.7.5")
APP_PHASE = 0


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "fixtures").is_dir() and (parent / "docs").is_dir():
            return parent
    return here.parents[4]


def fixtures_dir() -> Path:
    override = os.environ.get("YOKO_FIXTURES_DIR")
    return Path(override) if override else repo_root() / "fixtures"


@lru_cache(maxsize=1)
def git_sha() -> str:
    for var in ("GIT_SHA", "RAILWAY_GIT_COMMIT_SHA", "SOURCE_COMMIT"):
        value = os.environ.get(var)
        if value:
            return value
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root(),
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def fixture_manifest() -> list[dict[str, str]]:
    """Entries of fixtures/MANIFEST.sha256. `area` is `base` for the locked basic set."""
    path = fixtures_dir() / "MANIFEST.sha256"
    if not path.is_file():
        return []
    entries: list[dict[str, str]] = []
    for line in path.read_text().splitlines():
        digest, _, name = line.partition("  ")
        if not name:
            continue
        area = "base" if name.startswith("patterns/base/") else name.split("/", 1)[0]
        entries.append({"path": name, "sha256": digest, "area": area})
    return entries


def fixtures_hash() -> str | None:
    path = fixtures_dir() / "MANIFEST.sha256"
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def build_info() -> dict[str, Any]:
    return {
        "git_sha": git_sha(),
        "phase": APP_PHASE,
        "seamly2d_pin": SEAMLY2D_PIN,
        "pattern_formats_read": list(PATTERN_FORMATS_READ),
        "bundle_versions": {},  # prompt/tool bundles arrive in Phase 4+
        "fixtures_hash": fixtures_hash(),
    }
