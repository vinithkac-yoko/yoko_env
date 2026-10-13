"""Python behind the tools that are not a single Seamly2D element: variables, pieces and blocks,
the read tools and the library tools. Each takes the validated arguments and returns the common
result (`Toolbox.report` / `Toolbox.ok`)."""

from __future__ import annotations

import base64
from collections.abc import Mapping
from typing import Any, cast

from yoko_engine.copy_piece import CopyError, plan_copy_piece
from yoko_engine.formula import is_valid_name
from yoko_engine.geometry import Line
from yoko_engine.library import search
from yoko_engine.pieces_edit import NodeSpec, pieces_of
from yoko_engine.session import (
    ActionMeta,
    AddBlock,
    AddPiece,
    DeleteBlock,
    DeletePiece,
    DeleteVariable,
    PatternSession,
    RenameBlock,
    SetPiece,
    SetVariable,
)
from yoko_engine.units import from_pixel, px_to_mm
from yoko_io.render import render_png, render_svg

from yoko_tools.runtime import Handler, Toolbox, ToolError

MAX_LIST = 200


# -- variables ---------------------------------------------------------------------------------
def set_variable(box: Toolbox, args: Mapping[str, Any], meta: ActionMeta) -> dict[str, Any]:
    name = cast(str, args["name"])
    if not name.startswith("#") or not is_valid_name(name):
        raise ToolError(
            "invalid_name",
            f"{name!r} is not a good variable name",
            "name",
            "start with # and use letters, digits and underscores, for example #s1_hem_flare",
        )
    return box.apply(
        SetVariable(name, cast(str, args["formula"]), args.get("description", "")), meta
    )


def delete_variable(box: Toolbox, args: Mapping[str, Any], meta: ActionMeta) -> dict[str, Any]:
    return box.apply(DeleteVariable(cast(str, args["name"])), meta)


# -- pieces and blocks -------------------------------------------------------------------------
def _piece_id(session: PatternSession, ref: str, field: str = "piece") -> int:
    pieces = [
        (int(p.get("id") or 0), p.get("name") or "") for _, p, _ in pieces_of(session.pattern)
    ]
    ref = ref.strip()
    if ref.startswith("#") and ref[1:].isdigit():
        if any(i == int(ref[1:]) for i, _ in pieces):
            return int(ref[1:])
    else:
        same = [i for i, n in pieces if n == ref]
        if len(same) == 1:
            return same[0]
        if len(same) > 1:
            raise ToolError(
                "ambiguous_piece", f"{len(same)} pieces are called {ref!r}", field,
                "use #<id>: " + ", ".join(f"#{i}" for i in same),
            )  # fmt: skip
    names = ", ".join(n for _, n in pieces) or "none yet"
    raise ToolError("unknown_piece", f"there is no piece {ref!r}", field, f"pieces: {names}")


def _nodes(box: Toolbox, raw: list[Mapping[str, Any]]) -> tuple[NodeSpec, ...]:
    out: list[NodeSpec] = []
    for i, n in enumerate(raw):
        target = box.resolve(cast(str, n["object"]), "object", f"nodes[{i}].object")
        if target.kind == "object":
            raise ToolError(
                "wrong_kind",
                f"{n['object']!r} is not a point, curve or arc",
                f"nodes[{i}].object",
                "a piece is outlined by points and by the curves and arcs between them",
            )
        out.append(NodeSpec(target.id, bool(n.get("reverse", False))))
    return tuple(out)


def add_piece(box: Toolbox, args: Mapping[str, Any], meta: ActionMeta) -> dict[str, Any]:
    nodes = _nodes(box, cast("list[Mapping[str, Any]]", args["nodes"]))
    out = box.apply(AddPiece(cast(str, args["name"]), nodes), meta)
    if out["ok"]:
        pid = out["created"][0]["id"] if out["created"] else None
        out["data"] = {"piece_id": pid}
    return out


def set_piece(box: Toolbox, args: Mapping[str, Any], meta: ActionMeta) -> dict[str, Any]:
    pid = _piece_id(box.session, cast(str, args["piece"]))
    if "name" not in args and "nodes" not in args:
        raise ToolError("nothing_to_change", "give a new name or a new outline", None, None)
    nodes = _nodes(box, cast("list[Mapping[str, Any]]", args["nodes"])) if "nodes" in args else None
    return box.apply(SetPiece(pid, args.get("name"), nodes), meta)


def delete_piece(box: Toolbox, args: Mapping[str, Any], meta: ActionMeta) -> dict[str, Any]:
    return box.apply(DeletePiece(_piece_id(box.session, cast(str, args["piece"]))), meta)


def add_block(box: Toolbox, args: Mapping[str, Any], meta: ActionMeta) -> dict[str, Any]:
    return box.apply(AddBlock(cast(str, args["name"])), meta)


def rename_block(box: Toolbox, args: Mapping[str, Any], meta: ActionMeta) -> dict[str, Any]:
    return box.apply(RenameBlock(cast(str, args["block"]), cast(str, args["name"])), meta)


def delete_block(box: Toolbox, args: Mapping[str, Any], meta: ActionMeta) -> dict[str, Any]:
    return box.apply(DeleteBlock(cast(str, args["block"])), meta)


def undo(box: Toolbox, args: Mapping[str, Any], meta: ActionMeta) -> dict[str, Any]:
    return box.report(box.session.undo())


# -- read tools --------------------------------------------------------------------------------
def get_state(box: Toolbox, args: Mapping[str, Any], meta: ActionMeta) -> dict[str, Any]:
    scope = cast(str, args.get("scope", "summary"))
    s = box.session
    ev = s.evaluation
    pieces = [p.get("name") or "" for _, p, _ in pieces_of(s.pattern)]
    variables = [
        {"name": v.name, "formula": v.formula, "value": ev.symbols.get(v.name)}
        for v in s.pattern.variables
    ]
    issues = [
        {"severity": i.severity, "code": i.code, "message": i.message, "object_id": i.object_id}
        for i in ev.issues
    ]
    if scope == "variables":
        data: dict[str, Any] = {"variables": variables[:MAX_LIST], "count": len(variables)}
    elif scope == "pieces":
        data = {"pieces": pieces}
    elif scope == "problems":
        data = {"problems": issues[:MAX_LIST], "count": len(issues)}
    else:
        data = {
            "unit": s.pattern.unit,
            "blocks": [b.name for b in s.pattern.blocks],
            "objects": len(s.pattern.objects()),
            "points": len(ev.points),
            "curves": sum(1 for c in ev.curves.values() if c.drawn),
            "pieces": pieces,
            "variables": len(variables),
            "errors": sum(1 for i in ev.issues if i.severity == "error"),
            "warnings": sum(1 for i in ev.issues if i.severity != "error"),
            "state_hash": s.state_hash()[:16],
        }
    return box.ok(data)


def _tool_for(box: Toolbox, tag: str, kind: str | None) -> str | None:
    for spec in box.specs.values():
        e = spec.engine
        if spec.tier == "primitive" and e and e["tag"] == tag and e.get("type") == kind:
            return spec.name
    return None


def _describe(box: Toolbox, oid: int) -> dict[str, Any]:
    s = box.session
    ev = s.evaluation
    maker = box.maker(oid)
    row: dict[str, Any] = {"id": oid}
    if oid in ev.points:
        g = ev.points[oid]
        row |= {
            "kind": "point",
            "name": g.label,
            "x_mm": round(g.x_mm, 3),
            "y_mm": round(g.y_mm, 3),
        }
    elif oid in ev.curves:
        row |= {"kind": "curve", "name": ev.curves[oid].name}
    elif maker is not None:
        row |= {"kind": maker.tag, "name": f"#{oid}"}
    if maker is not None:
        row["tool"] = _tool_for(box, maker.tag, maker.get("type") if maker.get("type") else None)
    return row


def get_object(box: Toolbox, args: Mapping[str, Any], meta: ActionMeta) -> dict[str, Any]:
    target = box.resolve(cast(str, args["object"]), "object", "object")
    s = box.session
    ev = s.evaluation
    row = _describe(box, target.id)
    maker = box.maker(target.id)
    if maker is not None:
        row["attributes"] = {k: v for k, v in maker.attrs if k not in ("id", "type")}
    if target.id in ev.curves:
        geom = ev.curves[target.id].geom
        row["length"] = round(from_pixel(abs(geom.length()), s.pattern.unit), 4)
        row["unit"] = s.pattern.unit
    row["built_from"] = [_describe(box, i).get("name") for i in sorted(s.dependencies(target.id))]
    row["used_by"] = [_describe(box, i).get("name") for i in sorted(s.dependents(target.id))]
    row["history"] = [
        {"what": p.kind, "step": p.meta.step, "author": p.meta.author}
        for p in s.provenance(maker.id if maker else target.id)
    ]
    edit = f"edit_{row['tool']}" if row.get("tool") else None
    if edit in box.specs:
        row["edit_with"] = edit
        row["delete_with"] = f"delete_{row['tool']}"
    return box.ok(row)


def find_objects(box: Toolbox, args: Mapping[str, Any], meta: ActionMeta) -> dict[str, Any]:
    s = box.session
    ev = s.evaluation
    limit = int(args.get("limit", 40))
    kind = cast("str | None", args.get("kind"))
    text = cast(str, args.get("text", "")).lower()
    near = None
    within = float(args.get("within_mm", 50))
    if "near" in args:
        t = box.resolve(cast(str, args["near"]), "point", "near")
        near = ev.points[t.id]
    ids = [o.id for o in s.pattern.objects()]
    ids += [i for i in (*ev.points, *ev.curves) if i not in set(ids)]
    rows: list[dict[str, Any]] = []
    for oid in sorted(set(ids)):
        row = _describe(box, oid)
        if not row.get("name") and not row.get("kind"):
            continue
        if (
            kind
            and row.get("kind") != kind
            and not (kind == "operation" and row.get("kind") == "operation")
        ):
            continue
        if text and text not in str(row.get("name", "")).lower():
            continue
        if near is not None:
            if oid not in ev.points or oid == near.id:
                continue
            d = px_to_mm(Line(near.p, ev.points[oid].p).length())
            if d > within:
                continue
            row["distance_mm"] = round(d, 3)
        rows.append(row)
    return box.ok({"objects": rows[:limit], "count": len(rows), "truncated": len(rows) > limit})


def _names(box: Toolbox, ids: frozenset[int]) -> list[dict[str, Any]]:
    return [{"id": i, "name": _describe(box, i).get("name")} for i in sorted(ids)]


def dependents(box: Toolbox, args: Mapping[str, Any], meta: ActionMeta) -> dict[str, Any]:
    t = box.resolve(cast(str, args["object"]), "object", "object")
    return box.ok({"object": t.name, "used_by": _names(box, box.session.dependents(t.id))})


def dependencies(box: Toolbox, args: Mapping[str, Any], meta: ActionMeta) -> dict[str, Any]:
    t = box.resolve(cast(str, args["object"]), "object", "object")
    return box.ok({"object": t.name, "built_from": _names(box, box.session.dependencies(t.id))})


def measure(box: Toolbox, args: Mapping[str, Any], meta: ActionMeta) -> dict[str, Any]:
    s = box.session
    ev = s.evaluation
    unit = s.pattern.unit
    first = box.resolve(cast(str, args["from"]), "object", "from")
    if "to" in args:
        second = box.resolve(cast(str, args["to"]), "point", "to")
        if first.kind != "point":
            raise ToolError("wrong_kind", f"{first.name!r} is not a point", "from", None)
        line = Line(ev.points[first.id].p, ev.points[second.id].p)
        return box.ok(
            {
                "distance": round(from_pixel(line.length(), unit), 4),
                "unit": unit,
                "distance_mm": round(px_to_mm(line.length()), 3),
                "angle_deg": round(line.angle(), 4),
            }
        )
    if first.kind == "curve":
        length = abs(ev.curves[first.id].geom.length())
        return box.ok(
            {
                "length": round(from_pixel(length, unit), 4),
                "unit": unit,
                "length_mm": round(px_to_mm(length), 3),
            }
        )
    raise ToolError("need_second_point", "give `to`, or name a curve or arc", "to", None)


def list_measurements(box: Toolbox, args: Mapping[str, Any], meta: ActionMeta) -> dict[str, Any]:
    values = box.session.measurements
    return box.ok(
        {
            "unit": box.session.pattern.unit,
            "measurements": [{"name": k, "value": round(v, 4)} for k, v in sorted(values.items())],
        }
    )


def render(box: Toolbox, args: Mapping[str, Any], meta: ActionMeta) -> dict[str, Any]:
    width = int(args.get("width_px", 1000))
    if args.get("format", "svg") == "png":
        data = render_png(box.session.pattern, box.session.evaluation, width_px=width)
        return box.ok({"format": "png", "base64": base64.b64encode(data).decode()})
    svg = render_svg(box.session.pattern, box.session.evaluation, width_px=width)
    return box.ok({"format": "svg", "svg": svg})


# -- library -----------------------------------------------------------------------------------
def _library(box: Toolbox) -> Any:
    if box.library is None:
        raise ToolError("not_available", "there is no pattern library in this run")
    return box.library


def search_library(box: Toolbox, args: Mapping[str, Any], meta: ActionMeta) -> dict[str, Any]:
    metas = _library(box).metas()
    found = search(
        metas.values(),
        cast(str, args.get("brief", "")),
        tags=tuple(cast("list[str]", args.get("tags", ()))),
        garment_type=cast("str | None", args.get("garment_type")),
        limit=int(args.get("limit", 10)),
    )
    return box.ok(
        {
            "results": [
                {
                    "id": m.id,
                    "name": m.name,
                    "garment_type": m.garment_type,
                    "tags": list(m.tags),
                    "description": m.description,
                    "locked": m.locked,
                }
                for m in found
            ]
        }
    )


def load_pattern(box: Toolbox, args: Mapping[str, Any], meta: ActionMeta) -> dict[str, Any]:
    pid = cast(str, args["pattern"])
    session = _library(box).session(pid)
    box.loaded[pid] = session
    ev = session.evaluation
    return box.ok(
        {
            "pattern": pid,
            "objects": len(session.pattern.objects()),
            "points": len(ev.points),
            "pieces": [p.get("name") or "" for _, p, _ in pieces_of(session.pattern)],
        }
    )


def copy_piece_from(box: Toolbox, args: Mapping[str, Any], meta: ActionMeta) -> dict[str, Any]:
    pid = cast(str, args["pattern"])
    source = box.loaded.get(pid)
    if source is None:
        raise ToolError("not_loaded", f"{pid!r} is not loaded", "pattern", "use load_pattern first")
    piece = _piece_id(source, cast(str, args["piece"]))
    try:
        plan = plan_copy_piece(source, piece, box.session)
    except CopyError as err:
        raise ToolError(err.code, str(err), "piece", None) from None
    out = box.report(box.session.apply_all(plan.actions, meta))
    if out["ok"]:
        out["data"] = {"objects": plan.objects, "variables": list(plan.variables)}
    return out


HANDLERS: dict[str, Handler] = {
    "set_variable": set_variable,
    "delete_variable": delete_variable,
    "add_piece": add_piece,
    "set_piece": set_piece,
    "delete_piece": delete_piece,
    "add_block": add_block,
    "rename_block": rename_block,
    "delete_block": delete_block,
    "undo": undo,
    "get_state": get_state,
    "get_object": get_object,
    "find_objects": find_objects,
    "dependents": dependents,
    "dependencies": dependencies,
    "measure": measure,
    "list_measurements": list_measurements,
    "render": render,
    "search_library": search_library,
    "load_pattern": load_pattern,
    "copy_piece_from": copy_piece_from,
}
