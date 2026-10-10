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


COMMENT = "#comment"  # RawNode.tag of an XML comment; the comment text is `RawNode.text`
TEXT = "#text"  # RawNode.tag of character data between elements (rare; kept for the round trip)


@dataclass(frozen=True, slots=True)
class RawNode:
    """An XML element, comment or text we carry through unchanged.

    An element that holds only text keeps it in `text`. In an element with child elements, comments
    and any non-blank text are children with the tags `COMMENT` and `TEXT`.
    """

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
    # Attributes of <draftBlock> other than `name`.
    extra_attrs: Attrs = ()
    # Where <calculation> sits among the block's children (-1: the block has none).
    calculation_index: int = 0


@dataclass(frozen=True, slots=True)
class Pattern:
    unit: str  # cm, mm or inch
    version: str  # file format version read, e.g. "0.6.8"
    measurements_file: str
    variables: tuple[Variable, ...]
    blocks: tuple[DraftBlock, ...]
    # Everything else from the file (name, number, gradation, labels, ...), in order.
    header: tuple[RawNode, ...] = field(default=())
    # Order of the file's top-level children: ("raw", i) is header[i], ("variables", 0) the variable
    # section, ("block", i) blocks[i]. Blocks missing from it are written last.
    layout: tuple[tuple[str, int], ...] = ()
    line_ending: str = "\n"  # "\r\n" for files saved on Windows
    root_attrs: Attrs = ()  # attributes of <pattern> itself (readOnly)

    def objects(self) -> tuple[Obj, ...]:
        return tuple(o for b in self.blocks for o in b.objects)


@dataclass(frozen=True, slots=True)
class RawDocument:
    """A whole XML file carried through unchanged: the lossless side of a measurement file."""

    root_tag: str
    root_attrs: Attrs
    children: tuple[RawNode, ...]
    line_ending: str = "\n"
    declaration: str = '<?xml version="1.0" encoding="UTF-8"?>'


@dataclass(frozen=True, slots=True)
class Measurement:
    name: str
    base: float
    size_increase: float = 0.0
    height_increase: float = 0.0
    # Individual files may give a formula over other measurements, e.g.
    # "(height_neck_back - height_knee)"; `base` is then unused.
    formula: str = ""


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
    kind: str = "multisize"  # "multisize" (.smms) or "individual" (.smis): one person's values
    version: str = ""  # file format version read, e.g. "0.4.4"
    document: RawDocument | None = None  # the file as read, for writing it back unchanged

    def values(self, size: float | None = None, height: float | None = None) -> dict[str, float]:
        if self.kind == "individual":
            return self._individual_values()
        size = self.base_size if size is None else size
        height = self.base_height if height is None else height
        k_size = (size - self.base_size) / self.size_step_cm
        k_height = (height - self.base_height) / self.height_step_cm
        return {
            m.name: m.base + k_size * m.size_increase + k_height * m.height_increase
            for m in self.measurements
        }

    def _individual_values(self) -> dict[str, float]:
        """Individual values, resolving formulas that mention other measurements."""
        from yoko_engine.formula import (
            FormulaError,
            FormulaErrorCode,
            parse,
        )

        values = {m.name: m.base for m in self.measurements if not m.formula}
        pending = {m.name: parse(m.formula) for m in self.measurements if m.formula}
        while pending:
            progressed = False
            for name, f in list(pending.items()):
                if all(n in values for n in f.names):
                    values[name] = f.evaluate(values)
                    del pending[name]
                    progressed = True
            if not progressed:
                missing = sorted({n for f in pending.values() for n in f.names if n not in values})
                raise FormulaError(
                    FormulaErrorCode.UNDEFINED_NAME,
                    f"measurements {sorted(pending)} depend on {missing}, which are not defined "
                    "(or depend on each other in a loop)",
                    "; ".join(f"{n} = {f.text}" for n, f in pending.items()),
                )
        return values
