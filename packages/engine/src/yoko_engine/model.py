"""The pattern model: a program of construction objects.

A `Pattern` is metadata, a measurement binding, variables (Seamly2D "increments"), and drafting
blocks. Each block holds an ordered list of construction objects (`Obj`): points, lines, arcs,
curves and operations, each built from earlier objects plus formulas.

Design notes
------------
- Everything is immutable, so `fork()` can share structure and a state hash is stable.
- An `Obj` keeps **all** attributes of its Seamly2D element in file order (`attrs`), plus raw child
  elements. That is what makes the Seamly2D round trip lossless: nothing we do not understand is
  dropped, and display attributes (colour, line type, weight, label offsets) ride along untouched.
- The typed meaning of an attribute (an object reference, a formula, a plain number) comes from the
  kind table in `yoko_engine.kinds`.
- Object ids are Seamly2D's own numeric ids. They are the stable internal identity: references go by
  id, so renaming a label never breaks a reference. (No random UUIDs: they would break determinism.)
"""

from __future__ import annotations

from dataclasses import dataclass, field

Attrs = tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class RawNode:
    """An XML element we carry through unchanged."""

    tag: str
    attrs: Attrs = ()
    text: str = ""
    children: tuple[RawNode, ...] = ()

    def get(self, key: str, default: str | None = None) -> str | None:
        for k, v in self.attrs:
            if k == key:
                return v
        return default


@dataclass(frozen=True, slots=True)
class Obj:
    """One construction object (a point, line, arc, curve or operation)."""

    id: int
    tag: str  # XML element: point, line, arc, spline, operation, ...
    kind: str  # the `type` attribute (endLine, alongLine, ...); for a plain line, "line"
    attrs: Attrs
    children: tuple[RawNode, ...] = ()

    def get(self, key: str, default: str | None = None) -> str | None:
        for k, v in self.attrs:
            if k == key:
                return v
        return default

    def with_attr(self, key: str, value: str) -> Obj:
        """A copy with one attribute replaced (or appended if it was absent)."""
        out: list[tuple[str, str]] = []
        found = False
        for k, v in self.attrs:
            if k == key:
                out.append((k, value))
                found = True
            else:
                out.append((k, v))
        if not found:
            out.append((key, value))
        return Obj(self.id, self.tag, self.kind, tuple(out), self.children)

    @property
    def label(self) -> str:
        """The human-readable name (`A1`). Lines and curves have none and return ''."""
        return self.get("name", "") or ""


@dataclass(frozen=True, slots=True)
class Variable:
    """A pattern variable: Seamly2D `increment` (format 0.6.8) or `variable` (0.6.9 and later)."""

    name: str
    formula: str
    description: str = ""
    extra: Attrs = ()


@dataclass(frozen=True, slots=True)
class DraftBlock:
    name: str
    objects: tuple[Obj, ...]
    # Sections we do not interpret yet (modeling, pieces, groups, ...), kept for the round trip.
    sections: tuple[RawNode, ...] = ()


@dataclass(frozen=True, slots=True)
class Pattern:
    unit: str  # cm, mm or inch
    version: str  # file format version read, e.g. "0.6.8"
    measurements_file: str
    variables: tuple[Variable, ...]
    blocks: tuple[DraftBlock, ...]
    # Everything else from the file (name, number, gradation, labels, ...), in order.
    header: tuple[RawNode, ...] = field(default=())

    def objects(self) -> tuple[Obj, ...]:
        return tuple(o for b in self.blocks for o in b.objects)


@dataclass(frozen=True, slots=True)
class Measurement:
    name: str
    base: float
    size_increase: float = 0.0
    height_increase: float = 0.0


@dataclass(frozen=True, slots=True)
class MeasurementSet:
    """A multisize measurement table (Seamly2D `.smms`/`.vst`).

    `value(name, size, height)` follows Seamly2D's gradation formula
    (`MeasurementVariable::CalcValue`): size steps are 2 cm and height steps 6 cm.
    """

    unit: str
    base_size: float
    base_height: float
    measurements: tuple[Measurement, ...]
    size_step_cm: float = 2.0
    height_step_cm: float = 6.0

    def values(self, size: float | None = None, height: float | None = None) -> dict[str, float]:
        size = self.base_size if size is None else size
        height = self.base_height if height is None else height
        k_size = (size - self.base_size) / self.size_step_cm
        k_height = (height - self.base_height) / self.height_step_cm
        return {
            m.name: m.base + k_size * m.size_increase + k_height * m.height_increase
            for m in self.measurements
        }
