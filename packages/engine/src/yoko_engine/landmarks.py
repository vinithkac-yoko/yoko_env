"""Landmarks: standard pattern-making names for objects (docs/adr/0004-landmarks.md).

Plans, recipes and tools say `bodice_front.SNP`, not `C5`. A landmarks file maps each standard name
to an object in a pattern, by label (points) or by name (curves). This module resolves and validates
a mapping; reading the YAML sidecar file is `yoko_io.landmarks`.

The vocabulary itself comes from the pattern makers. Nothing here guesses it.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from yoko_engine.evaluator import Evaluation, Issue

NAME_RE = re.compile(r"^[a-z][a-z0-9_]*\.[A-Za-z][A-Za-z0-9_]*$")  # <piece>.<landmark>


@dataclass(frozen=True, slots=True)
class LandmarkRef:
    """Where a landmark points: a point label, a curve name, or an object id."""

    label: str | None = None
    object_id: int | None = None
    note: str = ""  # free text, e.g. the confidence of a best-guess mapping


@dataclass(frozen=True, slots=True)
class Landmarks:
    version: int
    entries: tuple[tuple[str, LandmarkRef], ...]

    @staticmethod
    def from_mapping(data: Mapping[str, object]) -> Landmarks:
        """Build from the parsed sidecar: `{"version": 1, "landmarks": {name: {label|id: ...}}}`."""
        version = data.get("version")
        if version != 1:
            raise ValueError(f"unsupported landmarks version {version!r}")
        raw_value = data.get("landmarks")
        if not isinstance(raw_value, Mapping):
            raise ValueError("'landmarks' must be a mapping of name to target")
        raw = cast(Mapping[object, object], raw_value)
        entries: list[tuple[str, LandmarkRef]] = []
        for name, target_value in raw.items():
            if not isinstance(name, str) or not NAME_RE.match(name):
                raise ValueError(f"bad landmark name {name!r}: use <piece>.<landmark>")
            if not isinstance(target_value, Mapping):
                raise ValueError(f"landmark {name}: target must be a mapping")
            target = cast(Mapping[str, object], target_value)
            label = target.get("label")
            oid = target.get("id")
            if (label is None) == (oid is None):
                raise ValueError(f"landmark {name}: give exactly one of 'label' or 'id'")
            entries.append(
                (
                    name,
                    LandmarkRef(
                        label=str(label) if label is not None else None,
                        object_id=int(str(oid)) if oid is not None else None,
                        note=str(target.get("note", "")),
                    ),
                )
            )
        return Landmarks(1, tuple(entries))

    def names(self) -> tuple[str, ...]:
        return tuple(n for n, _ in self.entries)

    def resolve(self, ev: Evaluation) -> tuple[dict[str, int], list[Issue]]:
        """Landmark name -> object id, and an issue for every landmark that does not resolve."""
        by_label = {g.label: g.id for g in ev.points.values() if g.label}
        by_curve = {c.name: c.id for c in ev.curves.values()}
        found: dict[str, int] = {}
        issues: list[Issue] = []
        for name, ref in self.entries:
            target: int | None = None
            if ref.object_id is not None:
                if ref.object_id in ev.points or ref.object_id in ev.curves:
                    target = ref.object_id
            elif ref.label is not None:
                target = by_label.get(ref.label, by_curve.get(ref.label))
            if target is None:
                what = f"label {ref.label!r}" if ref.label else f"id {ref.object_id}"
                issues.append(
                    Issue(
                        "landmark_unresolved",
                        f"landmark {name} points at {what}, which is not in the pattern",
                        None,
                        name,
                        "fix the landmarks file or the pattern",
                    )
                )
            else:
                found[name] = target
        return found, issues

    def label_for(self, name: str, ev: Evaluation) -> str | None:
        """The label of the object a landmark names (what a tool needs where it takes a label)."""
        resolved, _ = self.resolve(ev)
        oid = resolved.get(name)
        if oid is None:
            return None
        if oid in ev.points:
            return ev.points[oid].label
        return ev.curves[oid].name
