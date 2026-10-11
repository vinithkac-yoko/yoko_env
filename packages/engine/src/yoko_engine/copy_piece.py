"""Copy one piece, with everything it is drawn from, out of one pattern and into another.

`plan_copy_piece` works out which objects and variables the piece depends on (following every
reference, including the names of lines and curves used in formulas), gives the copies fresh ids,
and returns the actions that rebuild them in the destination: variables first, then the objects in
their original order, then the piece. Apply them with `PatternSession.apply_all` so that either all
of them land or none does. Labels are kept (formulas refer to them), so a label that the
destination already uses makes the copy fail rather than silently rename.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from yoko_engine.formula import FormulaError, parse
from yoko_engine.model import Obj, RawNode
from yoko_engine.pieces import piece_nodes as read_piece_nodes
from yoko_engine.pieces_edit import NodeSpec, next_id, pieces_of
from yoko_engine.session import (
    REF_ATTRS,
    Action,
    AddObject,
    AddPiece,
    PatternSession,
    SetVariable,
)

# attributes that name a point or curve an operation or tool *makes*, not one it reads
_OUTPUT_ATTRS = {"trueDarts": ("point1", "point2")}


class CopyError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class CopyPlan:
    actions: tuple[Action, ...]
    objects: int  # draft objects copied
    variables: tuple[str, ...]  # variables copied
    measurements: tuple[str, ...]  # measurements the copy needs (the destination must have them)


def _outputs(o: Obj) -> list[int]:
    """Ids of the points and curves an object makes besides its own id."""
    out: list[int] = []
    for key in _OUTPUT_ATTRS.get(o.kind, ()):
        raw = o.get(key)
        if raw is not None and raw.isdigit():
            out.append(int(raw))
    for group in o.children:
        if group.tag == "destination":
            out.extend(
                int(d.get("idObject") or "")
                for d in group.children
                if (d.get("idObject") or "").isdigit()
            )
    return out


def _piece(src: PatternSession, piece_id: int) -> tuple[RawNode, RawNode]:
    for _, piece, modeling in pieces_of(src.pattern):
        if piece.get("id") == str(piece_id):
            return piece, modeling
    raise CopyError("unknown_piece", f"there is no piece {piece_id}")


def _closure(src: PatternSession, wanted: set[int]) -> set[int]:
    """Every object the given ones are (transitively) built from, themselves included."""
    done: set[int] = set()
    todo = list(wanted)
    while todo:
        oid = todo.pop()
        if oid in done:
            continue
        done.add(oid)
        todo.extend(src.dependencies(oid))
    return done


def _variables_needed(src: PatternSession, objects: set[int]) -> list[str]:
    declared = {v.name: v for v in src.pattern.variables}
    needed: list[str] = []
    todo: list[str] = []
    for oid in objects:
        todo.extend(n for n in src.names_used(oid) if n in declared)
    while todo:
        name = todo.pop()
        if name in needed:
            continue
        needed.append(name)
        try:
            todo.extend(n for n in parse(declared[name].formula).names if n in declared)
        except FormulaError:
            continue
    order = {v.name: i for i, v in enumerate(src.pattern.variables)}
    return sorted(needed, key=lambda n: order[n])


def _measurements_needed(src: PatternSession, objects: set[int], variables: list[str]) -> list[str]:
    declared = {v.name for v in src.pattern.variables}
    names: set[str] = set()
    for oid in objects:
        names |= {n for n in src.names_used(oid) if n not in declared and n in src.measurements}
    by_name = {v.name: v for v in src.pattern.variables}
    for name in variables:
        try:
            names |= {n for n in parse(by_name[name].formula).names if n in src.measurements}
        except FormulaError:
            continue
    return sorted(names)


def _remap_obj(o: Obj, ids: dict[int, int]) -> Obj:
    def mapped(raw: str) -> str:
        return str(ids[int(raw)]) if raw.isdigit() and int(raw) in ids else raw

    attrs = tuple(
        (k, mapped(v) if k in REF_ATTRS or k in _OUTPUT_ATTRS.get(o.kind, ()) else v)
        for k, v in o.attrs
    )

    def remap_node(n: RawNode) -> RawNode:
        node_attrs = tuple(
            (k, mapped(v) if k in ("pSpline", "idObject") else v) for k, v in n.attrs
        )
        return replace(n, attrs=node_attrs, children=tuple(remap_node(c) for c in n.children))

    return replace(o, id=ids[o.id], attrs=attrs, children=tuple(remap_node(c) for c in o.children))


def plan_copy_piece(src: PatternSession, piece_id: int, dst: PatternSession) -> CopyPlan:
    """The actions that copy a piece (and what it depends on) from `src` into `dst`."""
    piece, modeling = _piece(src, piece_id)
    copies = {m.get("id"): m for m in modeling.children}
    wanted: set[int] = set()
    specs: list[tuple[int, bool]] = []
    producers: dict[int, int] = src.producers()
    for node in read_piece_nodes(piece):
        m = copies.get(str(node.id))
        source = int(m.get("idObject") or "0") if m is not None else 0
        if source == 0 or (
            source not in src.evaluation.points and source not in src.evaluation.curves
        ):
            raise CopyError(
                "unsupported_piece",
                f"piece {piece_id} uses objects a union or another piece made; copy the pieces it "
                "was united from instead",
            )
        wanted.add(producers.get(source, source))
        specs.append((source, node.reverse))

    objects = _closure(src, wanted)
    variables = _variables_needed(src, objects)
    measurements = _measurements_needed(src, objects, variables)
    missing = [m for m in measurements if m not in dst.measurements]
    if missing:
        raise CopyError(
            "missing_measurement",
            f"the destination has no measurement {', '.join(missing)}",
        )
    declared = {v.name: v for v in dst.pattern.variables}
    source_vars = {v.name: v for v in src.pattern.variables}
    for name in variables:
        if name in declared and declared[name].formula != source_vars[name].formula:
            raise CopyError(
                "variable_conflict",
                f"variable {name} is {declared[name].formula!r} in the destination but "
                f"{source_vars[name].formula!r} in the source",
            )

    ordered = [o for o in src.pattern.objects() if o.id in objects]
    labels = {g.label for g in dst.evaluation.points.values()}
    clash = sorted(o.label for o in ordered if o.label and o.label in labels)
    if clash:
        raise CopyError(
            "label_conflict",
            f"the destination already has points named {', '.join(clash[:8])}",
        )

    counter = next_id(dst.pattern)
    ids: dict[int, int] = {}
    for o in ordered:
        for old in (o.id, *_outputs(o)):
            if old not in ids:
                ids[old] = counter
                counter += 1

    actions: list[Action] = []
    for name in variables:
        if name not in declared:
            v = source_vars[name]
            actions.append(SetVariable(name, v.formula, v.description))
    actions.extend(AddObject(_remap_obj(o, ids)) for o in ordered)
    actions.append(
        AddPiece(
            piece.get("name") or "Copied piece",
            tuple(NodeSpec(ids[s], rev) for s, rev in specs),
        )
    )
    return CopyPlan(tuple(actions), len(ordered), tuple(variables), tuple(measurements))
