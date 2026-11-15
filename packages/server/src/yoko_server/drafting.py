"""Work items' patterns on the server: which measurements an item is seen at, the pattern at that
size, the drawing for the canvas and the inspector for one object.

The pattern lives here, not in the browser. In stage A an item is its starting pattern; from stage B
it is its starting pattern plus its action log, replayed. Evaluated patterns are kept in a small
cache, so switching sizes back and forth costs nothing after the first time.
"""

from __future__ import annotations

import re
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, cast

import yaml
from yoko_engine.binding import SizePoint, size_grid
from yoko_engine.landmarks import Landmarks
from yoko_engine.model import MeasurementSet, Pattern
from yoko_engine.session import PatternSession
from yoko_io.render import scene_data
from yoko_io.seamly import read_measurements
from yoko_tools.runtime import Toolbox
from yoko_tools.spec import ToolSpec, all_tools

from yoko_server.buildinfo import repo_root
from yoko_server.library import library


class DraftingError(ValueError):
    """A request the drafting routes cannot serve (an unknown size, a bad file)."""


@dataclass(frozen=True, slots=True)
class SizeOption:
    """One entry of the size switcher."""

    key: str  # "table:34:164" or "person:3"
    label: str
    values: Mapping[str, float]


@lru_cache(maxsize=1)
def specs() -> dict[str, ToolSpec]:
    return all_tools(repo_root() / "config/tools")


@lru_cache(maxsize=8)
def start(pattern_id: str) -> tuple[Pattern, MeasurementSet, str]:
    """A library pattern, its multisize table, and how its sizes are named."""
    _, pattern, table = library().load(pattern_id)
    return pattern, table, _size_label(pattern_id)


def _size_label(pattern_id: str) -> str:
    """The meta file's `size_label` ("UK {size}"), or nothing."""
    for area in ("base", "styles"):
        path = repo_root() / "library" / area / f"{pattern_id}.meta.yaml"
        if path.is_file():
            data = cast("Mapping[str, Any]", yaml.safe_load(path.read_text()) or {})
            return str(data.get("size_label") or "")
    return ""


COMING = ("reshape_neckline", "hem_shaping")  # being written by Kasi (ADR 0017)


def known_recipes() -> list[str]:
    """Recipe names from docs/manipulations/*.md (their `Recipe name:` line), plus COMING."""
    found: set[str] = set(COMING)
    for path in (repo_root() / "docs/manipulations").glob("*.md"):
        m = re.search(r"Recipe name: `([a-z][a-z0-9_]*)`", path.read_text())
        if m:
            found.add(m.group(1))
    return sorted(found)


def person_table(content: str) -> MeasurementSet:
    """A person's own measurement file (.smis) as uploaded; DraftingError if it is not one."""
    try:
        table = read_measurements(content.encode())
    except Exception as err:
        raise DraftingError(f"not a Seamly2D measurement file: {err}") from None
    if table.kind != "individual":
        raise DraftingError("this is a multisize table; upload one person's own file (.smis)")
    return table


def size_options(
    pattern_id: str, people: Mapping[int, tuple[str, MeasurementSet]]
) -> list[SizeOption]:
    """The table's sizes (sizes with the same numbers shown once) and every person's file."""
    pattern, table, label_format = start(pattern_id)
    grid = size_grid(pattern, table)

    def numbers(p: SizePoint) -> tuple[tuple[str, float], ...]:
        return tuple(sorted(p.values.items()))

    per_size: dict[float, set[tuple[tuple[str, float], ...]]] = {}
    groups: dict[tuple[tuple[str, float], ...], list[SizePoint]] = {}
    for p in grid:
        per_size.setdefault(p.size, set()).add(numbers(p))
        groups.setdefault(numbers(p), []).append(p)
    out: list[SizeOption] = []
    for same in groups.values():
        # one entry for sizes with the same numbers, named by the base height if it is among them
        p = next((q for q in same if q.height == table.base_height), same[0])
        name = f"size {p.size:g}"
        if label_format and "size" in p.values:
            name = f"{label_format.format(size=f'{p.values["size"]:g}')} ({name})"
        if len(per_size[p.size]) > 1:  # the table grades by height: say which height
            name += f", height {p.height:g}"
        out.append(SizeOption(f"table:{p.size:g}:{p.height:g}", name, p.values))
    for pid, (name, person) in sorted(people.items()):
        out.append(SizeOption(f"person:{pid}", name, person.values()))
    return out


def option_for(
    key: str, pattern_id: str, people: Mapping[int, tuple[str, MeasurementSet]]
) -> SizeOption:
    """The size a key names. A size and height of the table that the switcher shows under another
    entry (same numbers) is that entry."""
    options = size_options(pattern_id, people)
    for opt in options:
        if opt.key == key:
            return opt
    m = re.fullmatch(r"table:([\d.]+):([\d.]+)", key)
    if m:
        pattern, table, _ = start(pattern_id)
        size, height = float(m.group(1)), float(m.group(2))
        if any(p.size == size and p.height == height for p in size_grid(pattern, table)):
            values = table.values(size, height)
            for opt in options:
                if dict(opt.values) == values:
                    return opt
    raise DraftingError(f"there is no size {key!r} for this item")


def default_key(measurements: Mapping[str, Any], pattern_id: str) -> str:
    if measurements.get("kind") == "person":
        return f"person:{measurements['id']}"
    _, table, _ = start(pattern_id)
    size = measurements.get("size")
    height = measurements.get("height")
    size = table.base_size if size is None else size
    height = table.base_height if height is None else height
    return f"table:{float(size):g}:{float(height):g}"


class Sessions:
    """Evaluated patterns by (item, state, size), the most recent few kept."""

    def __init__(self, keep: int = 48) -> None:
        self.keep = keep
        self._cache: OrderedDict[tuple[int, str, str], Toolbox] = OrderedDict()

    def get(self, item_id: int, state: str, pattern: Pattern, option: SizeOption) -> Toolbox:
        key = (item_id, state, option.key)
        box = self._cache.get(key)
        if box is None:
            session = PatternSession(pattern, dict(option.values), read_only=True)
            box = Toolbox(session, specs(), landmarks=landmarks())
            self._cache[key] = box
            while len(self._cache) > self.keep:
                self._cache.popitem(last=False)
        else:
            self._cache.move_to_end(key)
        return box

    def forget(self, item_id: int) -> None:
        for key in [k for k in self._cache if k[0] == item_id]:
            del self._cache[key]


@lru_cache(maxsize=1)
def landmarks() -> Landmarks | None:
    """Confirmed landmarks of the basic set. None so far: the names in docs/landmarks are
    proposals, and nothing may use them until a pattern maker has confirmed them."""
    return None


@lru_cache(maxsize=1)
def proposed_names() -> dict[str, list[str]]:
    """Proposed (unverified) landmark names by Seamly2D label, shown only on request and marked
    as proposals."""
    out: dict[str, list[str]] = {}
    root = repo_root() / "docs/landmarks"
    outline = root / "proposed_names.yaml"
    if outline.is_file():
        data = cast("Mapping[str, Any]", yaml.safe_load(outline.read_text()))
        for entries in cast(
            "Mapping[str, Mapping[int, Mapping[str, str]]]", data["pieces"]
        ).values():
            for e in entries.values():
                out.setdefault(e["label"], []).append(e["name"])
    internal = root / "proposed_internal.yaml"
    if internal.is_file():
        data = cast("Mapping[str, Any]", yaml.safe_load(internal.read_text()))
        for rows in cast("Mapping[str, list[Mapping[str, str]]]", data["pieces"]).values():
            for e in rows:
                if e.get("kind") == "point":
                    out.setdefault(e["label"], []).append(e["name"])
    return out


def scene(box: Toolbox) -> dict[str, Any]:
    """The drawing for the canvas, with the proposed landmark names of each labelled object."""
    data = scene_data(box.session.pattern, box.session.evaluation)
    names = proposed_names()
    data["proposed_landmarks"] = {
        str(p["id"]): names[p["label"]] for p in data["points"] if p["label"] in names
    }
    for c in data["curves"]:
        if c["name"] in names:
            data["proposed_landmarks"][str(c["id"])] = names[c["name"]]
    data["errors"] = [
        {"code": i.code, "message": i.message, "object_id": i.object_id}
        for i in box.session.issues()
        if i.severity == "error"
    ]
    return data


def inspect(box: Toolbox, object_id: int) -> dict[str, Any]:
    """One object: how it was made (its formulas), where it is, what it is built from and what is
    built from it."""
    result = box.call("get_object", {"object": f"#{object_id}"})
    if not result["ok"]:
        raise DraftingError(result["error"]["message"])
    data = dict(result["data"])
    ev = box.session.evaluation
    if object_id in ev.points:
        g = ev.points[object_id]
        data["x_mm"], data["y_mm"] = round(g.x_mm, 3), round(g.y_mm, 3)
    data["proposed_landmarks"] = proposed_names().get(str(data.get("name", "")), [])
    return data


def object_ids(box: Toolbox) -> set[int]:
    ev = box.session.evaluation
    return {*ev.points, *ev.curves, *(o.id for o in box.session.pattern.objects())}


def check_object(box: Toolbox, object_id: int) -> None:
    if object_id not in object_ids(box):
        raise DraftingError(f"there is no object {object_id} in this item")
