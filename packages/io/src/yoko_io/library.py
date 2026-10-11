"""The pattern library on disk.

    <root>/base/<id>.meta.yaml      locked patterns; `pattern` and `measurements` may start with
                                    `{fixtures}`, the fixtures directory
    <root>/styles/<id>.meta.yaml    patterns people (and agents) derive from them
    <root>/styles/<id>.sm2d         the pattern file, written back in the format it was read in

The metadata (parent, description, garment type, tags) lives beside the pattern, never inside it,
so a pattern file stays exactly what Seamly2D wrote. Storage sits behind this class so a database
can replace it later (Phase 6) without touching the engine.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import cast

import yaml
from yoko_engine.library import AREAS, LibraryError, PatternMeta, check_meta
from yoko_engine.model import MeasurementSet, Pattern
from yoko_engine.session import PatternSession

from yoko_io.seamly import read_measurements, read_pattern, write_pattern

_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


class LockedError(LibraryError):
    """A write to a base pattern was refused."""

    def __init__(self, pattern_id: str) -> None:
        super().__init__("locked", f"{pattern_id} is a base pattern and cannot be changed")


@dataclass(frozen=True, slots=True)
class Entry:
    meta: PatternMeta
    pattern_path: Path
    measurements_path: Path


class DirectoryLibrary:
    def __init__(self, root: Path, fixtures: Path) -> None:
        self.root = Path(root)
        self.fixtures = Path(fixtures)

    # -- reading ----------------------------------------------------------------------------
    def _resolve(self, text: str, meta_dir: Path) -> Path:
        text = text.replace("{fixtures}", str(self.fixtures))
        path = Path(text)
        return path if path.is_absolute() else meta_dir / path

    def entries(self) -> dict[str, Entry]:
        found: dict[str, Entry] = {}
        for area in AREAS:
            for meta_file in sorted((self.root / area).glob("*.meta.yaml")):
                raw: object = yaml.safe_load(meta_file.read_text())
                if not isinstance(raw, dict):
                    raise LibraryError("bad_meta", f"{meta_file.name}: not a mapping")
                data = cast(dict[str, object], raw)
                pid = str(data.get("id", ""))
                if not _ID.match(pid):
                    raise LibraryError("bad_id", f"{meta_file.name}: bad id {pid!r}")
                if pid in found:
                    raise LibraryError("duplicate_id", f"{pid} is defined twice")
                tags = data.get("tags") or []
                if not isinstance(tags, list):
                    raise LibraryError("bad_meta", f"{pid}: tags must be a list")
                parent = data.get("parent")
                meta = PatternMeta(
                    id=pid,
                    name=str(data.get("name", pid)),
                    area=area,
                    parent=str(parent) if parent else None,
                    description=" ".join(str(data.get("description", "")).split()),
                    garment_type=str(data.get("garment_type", "")),
                    tags=tuple(str(t) for t in cast(list[object], tags)),
                    measurements=str(data.get("measurements", "")),
                )
                pattern_text = str(data.get("pattern") or f"{pid}.sm2d")
                found[pid] = Entry(
                    meta,
                    self._resolve(pattern_text, meta_file.parent),
                    self._resolve(meta.measurements, meta_file.parent)
                    if meta.measurements
                    else Path(),
                )
        check_meta({k: e.meta for k, e in found.items()})
        return found

    def metas(self) -> dict[str, PatternMeta]:
        return {k: e.meta for k, e in self.entries().items()}

    def entry(self, pattern_id: str) -> Entry:
        try:
            return self.entries()[pattern_id]
        except KeyError:
            raise LibraryError("unknown_pattern", f"there is no pattern {pattern_id!r}") from None

    def load(self, pattern_id: str) -> tuple[PatternMeta, Pattern, MeasurementSet]:
        e = self.entry(pattern_id)
        return e.meta, read_pattern(e.pattern_path), read_measurements(e.measurements_path)

    def session(self, pattern_id: str) -> PatternSession:
        """A session on the pattern; base patterns are locked (the session refuses edits)."""
        meta, pattern, table = self.load(pattern_id)
        session = PatternSession(pattern, table, read_only=meta.locked)
        return session

    # -- writing ----------------------------------------------------------------------------
    def derive(
        self,
        parent_id: str,
        new_id: str,
        name: str,
        *,
        description: str = "",
        garment_type: str | None = None,
        tags: tuple[str, ...] | None = None,
    ) -> PatternMeta:
        """A new style: a copy of the parent's file (byte for byte), linked to it."""
        entries = self.entries()
        if parent_id not in entries:
            raise LibraryError("unknown_pattern", f"there is no pattern {parent_id!r}")
        if not _ID.match(new_id):
            raise LibraryError("bad_id", "an id is lower-case letters, digits and dashes")
        if new_id in entries:
            raise LibraryError("duplicate_id", f"{new_id} already exists")
        if not name.strip():
            raise LibraryError("empty_name", "a pattern needs a name")
        parent = entries[parent_id]
        styles = self.root / "styles"
        styles.mkdir(parents=True, exist_ok=True)
        (styles / f"{new_id}.sm2d").write_bytes(parent.pattern_path.read_bytes())
        meta = replace(
            parent.meta,
            id=new_id,
            name=name,
            area="styles",
            parent=parent_id,
            description=description,
            garment_type=parent.meta.garment_type if garment_type is None else garment_type,
            tags=parent.meta.tags if tags is None else tags,
        )
        self._write_meta(meta)
        return meta

    def update_meta(
        self,
        pattern_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        garment_type: str | None = None,
        tags: tuple[str, ...] | None = None,
    ) -> PatternMeta:
        entry = self.entry(pattern_id)
        if entry.meta.locked:
            raise LockedError(pattern_id)
        meta = replace(
            entry.meta,
            name=entry.meta.name if name is None else name,
            description=entry.meta.description if description is None else description,
            garment_type=entry.meta.garment_type if garment_type is None else garment_type,
            tags=entry.meta.tags if tags is None else tags,
        )
        self._write_meta(meta)
        return meta

    def save(self, pattern_id: str, pattern: Pattern) -> None:
        """Write a style's pattern back. A base pattern is never written."""
        entry = self.entry(pattern_id)
        if entry.meta.locked:
            raise LockedError(pattern_id)
        entry.pattern_path.write_bytes(write_pattern(pattern))

    def _write_meta(self, meta: PatternMeta) -> None:
        data: Mapping[str, object] = {
            "id": meta.id,
            "name": meta.name,
            "parent": meta.parent,
            "description": meta.description,
            "garment_type": meta.garment_type,
            "tags": list(meta.tags),
            "pattern": f"{meta.id}.sm2d",
            "measurements": meta.measurements,
        }
        path = self.root / meta.area / f"{meta.id}.meta.yaml"
        path.write_text(yaml.safe_dump(dict(data), sort_keys=False, allow_unicode=True))
