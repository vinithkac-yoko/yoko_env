"""The tool runtime: a tool call becomes actions on a `PatternSession`.

    box = Toolbox(session, all_tools(Path("config/tools")))
    box.call("point_origin", {"label": "A", "x": 1, "y": 1})

Every call returns one dictionary, the same shape for every tool:

    {ok, created, changed, deleted, warnings, error?: {code, field, message, hint}, diff}

Arguments are checked against the tool's schema first. Objects are named by label (a point), by name
(a curve or an arc), by `#<id>` (anything, a line for example) or by landmark name; every such name
is resolved here, so the engine only ever sees ids.
"""

from __future__ import annotations

import difflib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, cast

from yoko_engine.landmarks import Landmarks
from yoko_engine.library import LibraryError
from yoko_engine.model import Obj, RawNode
from yoko_engine.pieces_edit import next_id
from yoko_engine.session import (
    Action,
    ActionError,
    ActionMeta,
    AddObject,
    DeleteObject,
    PatternSession,
    Result,
    SetAttrs,
)

from yoko_tools.numbers import fmt_number
from yoko_tools.plan import section_parts
from yoko_tools.spec import SpecError, ToolSpec, template_params

Handler = Callable[["Toolbox", Mapping[str, Any], ActionMeta], dict[str, Any]]


class ToolError(Exception):
    """A call that cannot be carried out; becomes the `error` of the result."""

    def __init__(
        self, code: str, message: str, field: str | None = None, hint: str | None = None
    ) -> None:
        super().__init__(message)
        self.code, self.field, self.hint = code, field, hint

    def payload(self) -> dict[str, Any]:
        return {"code": self.code, "field": self.field, "message": str(self), "hint": self.hint}


@dataclass(frozen=True, slots=True)
class Target:
    """An object a name resolved to."""

    id: int
    kind: str  # "point" | "curve" | "object"
    name: str


class Toolbox:
    def __init__(
        self,
        session: PatternSession,
        specs: Mapping[str, ToolSpec],
        *,
        landmarks: Landmarks | None = None,
        handlers: Mapping[str, Handler] | None = None,
        library: Any = None,
    ) -> None:
        from yoko_tools.handlers import HANDLERS

        self.session = session
        self.specs = dict(specs)
        self.landmarks = landmarks
        self.handlers: dict[str, Handler] = {**HANDLERS, **(handlers or {})}
        self.library = library
        self.loaded: dict[str, PatternSession] = {}  # library patterns opened with load_pattern

    # -- names -> ids ---------------------------------------------------------------------------
    def resolve(self, name: str, kind: str, field: str) -> Target:
        """The object a name stands for, which must be of the given kind (`point`, `curve` or
        `object`)."""
        ev = self.session.evaluation
        name = name.strip()
        found: Target | None = None
        if name.startswith("#") and name[1:].isdigit():
            oid = int(name[1:])
            known = (
                oid in ev.points
                or oid in ev.curves
                or any(o.id == oid for o in self.session.pattern.objects())
            )
            if known:
                found = self._target(oid)
        elif self.landmarks is not None and "." in name:
            ids, _ = self.landmarks.resolve(ev)
            if name in ids:
                found = self._target(ids[name])
        if found is None:
            for g in ev.points.values():
                if g.label == name:
                    found = Target(g.id, "point", g.label)
                    break
        if found is None:
            for c in ev.curves.values():
                if c.name == name:
                    found = Target(c.id, "curve", c.name)
                    break
        if found is None:
            raise ToolError(
                "unknown_reference",
                f"there is no {'point' if kind == 'point' else 'object'} called {name!r}",
                field,
                self._suggest(name, kind),
            )
        if kind == "point" and found.kind != "point":
            raise ToolError(
                "wrong_kind", f"{name!r} is a {found.kind}, not a point", field, "name a point"
            )
        if kind == "curve" and found.kind != "curve":
            raise ToolError(
                "wrong_kind", f"{name!r} is a {found.kind}, not a curve or an arc", field,
                "name a curve or an arc by its name, for example Spl_A_B or Arc_A_12",
            )  # fmt: skip
        return found

    def _target(self, oid: int) -> Target:
        ev = self.session.evaluation
        if oid in ev.points:
            return Target(oid, "point", ev.points[oid].label)
        if oid in ev.curves:
            return Target(oid, "curve", ev.curves[oid].name)
        return Target(oid, "object", f"#{oid}")

    def _suggest(self, name: str, kind: str) -> str:
        ev = self.session.evaluation
        pool = [g.label for g in ev.points.values() if g.label]
        if kind != "point":
            pool += [c.name for c in ev.curves.values()]
        close = difflib.get_close_matches(name, pool, n=3, cutoff=0.6)
        if close:
            return "did you mean " + ", ".join(close) + "?"
        return "list the objects with find_objects to see the names"

    def maker(self, oid: int) -> Obj | None:
        """The object of the pattern that made a point or curve (an operation makes several)."""
        made_by = self.session.producers().get(oid, oid)
        for o in self.session.pattern.objects():
            if o.id == made_by:
                return o
        return None

    # -- calling --------------------
    def call(
        self, name: str, args: Mapping[str, Any] | None = None, meta: ActionMeta | None = None
    ) -> dict[str, Any]:
        meta = meta or ActionMeta()
        try:
            spec = self.specs.get(name)
            if spec is None:
                close = difflib.get_close_matches(name, list(self.specs), n=3, cutoff=0.6)
                raise ToolError(
                    "unknown_tool",
                    f"there is no tool {name!r}",
                    None,
                    ("did you mean " + ", ".join(close) + "?") if close else None,
                )
            try:
                clean = spec.validate(args or {})
            except SpecError as err:
                text = str(err)
                field = text.split(":", 1)[0]
                raise ToolError(
                    "invalid_arguments", text, field, f"see the parameters of {name}"
                ) from None
            return self._dispatch(spec, clean, meta)
        except ToolError as err:
            return self._failed(err.payload())
        except LibraryError as err:
            return self._failed(
                {"code": err.code, "field": None, "message": str(err), "hint": None}
            )

    def _dispatch(
        self, spec: ToolSpec, args: Mapping[str, Any], meta: ActionMeta
    ) -> dict[str, Any]:
        if spec.tier == "edit":
            return self._edit(spec, args, meta)
        if spec.tier == "delete":
            return self._delete(spec, args, meta)
        if spec.tier == "primitive":
            return self._create(spec, args, meta)
        handler = self.handlers.get(spec.handler or "")
        if handler is None:
            raise ToolError("not_available", f"{spec.name} has no implementation in this run")
        return handler(self, args, meta)

    # -- primitives --------------------
    def _resolved(self, spec: ToolSpec, args: Mapping[str, Any]) -> dict[str, Any]:
        """Arguments with every name replaced by an object id (as text)."""
        out: dict[str, Any] = dict(args)
        refs = dict(spec.refs())
        if (spec.engine or {}).get("builder") == "spline_path":
            refs["points"] = "point"
        for key, kind in refs.items():
            if key not in args:
                continue
            value = args[key]
            if isinstance(value, list) and value and isinstance(value[0], dict):
                out[key] = [
                    {
                        **e,
                        "point": str(
                            self.resolve(cast(str, e["point"]), kind, f"{key}[{i}].point").id
                        ),
                    }
                    for i, e in enumerate(cast("list[dict[str, Any]]", value))
                ]
            elif isinstance(value, list):
                from yoko_tools.sections import section_ids

                ids: list[str] = []
                for i, v in enumerate(cast("list[Any]", value)):
                    if kind == "object" and section_parts(cast(str, v)) is not None:
                        ids += [str(x) for x in section_ids(self, cast(str, v), f"{key}[{i}]")]
                    else:
                        ids.append(str(self.resolve(cast(str, v), kind, f"{key}[{i}]").id))
                out[key] = list(dict.fromkeys(ids))  # a section may repeat an object
            else:
                out[key] = str(self.resolve(cast(str, value), kind, key).id)
        return out

    def _attrs(self, spec: ToolSpec, args: Mapping[str, Any]) -> list[tuple[str, str]]:
        assert spec.engine is not None
        attrs: list[tuple[str, str]] = []
        for attr, rule in cast(Mapping[str, Any], spec.engine.get("set", {})).items():
            value = _render(rule, args)
            if value is not None:
                attrs.append((attr, value))
        return attrs

    def _create(self, spec: ToolSpec, args: Mapping[str, Any], meta: ActionMeta) -> dict[str, Any]:
        assert spec.engine is not None
        resolved = self._resolved(spec, args)
        new_id = next_id(self.session.pattern)
        builder = spec.engine["builder"]
        tag = cast(str, spec.engine["tag"])
        kind = cast("str | None", spec.engine.get("type"))
        head: list[tuple[str, str]] = [("id", str(new_id))]
        if kind:
            head.append(("type", kind))
        children: tuple[RawNode, ...] = ()
        attrs = self._attrs(spec, resolved)
        if builder == "true_darts":
            attrs += [("point1", str(new_id + 1)), ("point2", str(new_id + 2))]
        elif builder == "operation":
            children = self._operation_children(resolved, new_id)
        elif builder in ("spline_path", "bezier_path"):
            children = _path_children(builder, resolved)
        obj = Obj(new_id, tag, kind or tag, (*head, *attrs), children)
        return self._apply(AddObject(obj), meta)

    def _operation_children(self, resolved: Mapping[str, Any], op_id: int) -> tuple[RawNode, ...]:
        sources = cast("list[str]", resolved["sources"])
        ev = self.session.evaluation
        items: list[RawNode] = []
        dests: list[RawNode] = []
        for i, sid in enumerate(sources):
            items.append(
                RawNode(
                    "item",
                    (
                        ("alias", ""),
                        ("color", "black"),
                        ("idObject", sid),
                        ("lineType", "solidLine"),
                    ),
                )
            )
            attrs: tuple[tuple[str, str], ...] = (("idObject", str(op_id + 1 + i)),)
            if int(sid) in ev.points:
                attrs += (("mx", "0.132292"), ("my", "0.264583"), ("showPointName", "true"))
            dests.append(RawNode("item", attrs))
        return (
            RawNode("source", children=tuple(items)),
            RawNode("destination", children=tuple(dests)),
        )

    # -- edit and delete --------------------
    def _owner(self, spec: ToolSpec, target_name: str) -> tuple[Target, Obj]:
        assert spec.engine is not None
        target = self.resolve(target_name, "object", "target")
        obj = self.maker(target.id)
        want = spec.derived_from or spec.name
        if (
            obj is None
            or obj.tag != spec.engine["tag"]
            or obj.get("type") != spec.engine.get("type")
        ):
            made = f"{obj.tag}/{obj.kind}" if obj is not None else "nothing in the pattern"
            raise ToolError(
                "wrong_tool",
                f"{target_name!r} was not made with {want} (it comes from {made})",
                "target",
                "use the edit or delete tool that matches how the object was made",
            )
        return target, obj

    def _edit(self, spec: ToolSpec, args: Mapping[str, Any], meta: ActionMeta) -> dict[str, Any]:
        assert spec.engine is not None
        _, obj = self._owner(spec, cast(str, args["target"]))
        resolved = self._resolved(spec, {k: v for k, v in args.items() if k != "target"})
        changes: list[tuple[str, str]] = []
        for attr, rule in cast(Mapping[str, Any], spec.engine.get("set", {})).items():
            value = _render(rule, resolved)
            if value is not None:
                changes.append((attr, value))
        if not changes:
            raise ToolError(
                "nothing_to_change", "give at least one parameter to change", None, None
            )
        return self._apply(SetAttrs(obj.id, tuple(changes)), meta)

    def _delete(self, spec: ToolSpec, args: Mapping[str, Any], meta: ActionMeta) -> dict[str, Any]:
        _, obj = self._owner(spec, cast(str, args["target"]))
        return self._apply(DeleteObject(obj.id), meta)

    # -- results --------------------
    def apply(self, action: Action, meta: ActionMeta) -> dict[str, Any]:
        """Apply any session action and report it in the common result shape."""
        return self._apply(action, meta)

    def _apply(self, action: Action, meta: ActionMeta) -> dict[str, Any]:
        result = self.session.apply(action, meta)
        return self.report(result)

    def ok(self, data: Mapping[str, Any]) -> dict[str, Any]:
        """The result of a tool that only reads: the common shape, with the answer in `data`."""
        return {
            "ok": True,
            "created": [],
            "changed": [],
            "deleted": [],
            "warnings": [],
            "diff": {},
            "data": dict(data),
        }

    def report(self, result: Result) -> dict[str, Any]:
        ev = self.session.evaluation
        created: list[dict[str, Any]] = []
        for oid in result.created:
            created.extend(self._describe(oid))
        if not result.ok:
            err = result.error
            assert err is not None
            return self._failed(_error_dict(err))
        return {
            "ok": True,
            "created": created,
            "changed": [self._label(i) for i in result.changed],
            "deleted": list(result.deleted),
            "warnings": [
                {"code": w.code, "message": w.message, "object_id": w.object_id}
                for w in result.warnings
            ],
            "diff": {
                "moved": {
                    "count": result.moved.count,
                    "top": [{"label": n, "mm": round(mm, 3)} for n, mm in result.moved.top],
                },
                "objects": len(self.session.pattern.objects()),
                "errors": sum(1 for i in ev.issues if i.severity == "error"),
                "state_hash": self.session.state_hash()[:16],
            },
        }

    def _label(self, oid: int) -> dict[str, Any]:
        t = self._target(oid)
        return {"id": oid, "name": t.name}

    def _describe(self, oid: int) -> list[dict[str, Any]]:
        """What a new object made: itself and, for a point, where it is."""
        ev = self.session.evaluation
        out: list[dict[str, Any]] = []
        made = [oid] + [
            i for i, owner in self.session.producers().items() if owner == oid and i != oid
        ]
        for i in sorted(made):
            if i in ev.points:
                g = ev.points[i]
                out.append(
                    {
                        "id": i,
                        "kind": "point",
                        "name": g.label,
                        "x_mm": round(g.x_mm, 3),
                        "y_mm": round(g.y_mm, 3),
                    }
                )
            elif i in ev.curves:
                out.append({"id": i, "kind": "curve", "name": ev.curves[i].name})
        if not out:
            out.append({"id": oid, "kind": "object", "name": f"#{oid}"})
        return out

    @staticmethod
    def _failed(error: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "ok": False,
            "created": [],
            "changed": [],
            "deleted": [],
            "warnings": [],
            "error": dict(error),
            "diff": {},
        }


def _error_dict(err: ActionError) -> dict[str, Any]:
    return {"code": err.code, "field": err.field, "message": err.message, "hint": err.hint}


def _render(rule: Any, args: Mapping[str, Any]) -> str | None:
    """The attribute value for one `set` rule, or None when the attribute is to be left out."""
    if isinstance(rule, dict):
        spec = cast(Mapping[str, Any], rule)
        if "param" in spec:
            param = cast(str, spec["param"])
            if param not in args:
                return None
            raw = args[param]
            if "map" in spec:
                key = str(raw).lower() if isinstance(raw, bool) else str(raw)
                return cast("str | None", spec["map"].get(key))
            if "omit_if" in spec and str(raw) == str(spec["omit_if"]):
                return None
            return _text(raw)
        raise ToolError("bad_tool_file", f"cannot render rule {spec!r}")
    template = cast(str, rule)
    names = template_params(template)
    if any(n not in args for n in names):
        return None
    out = template
    for n in names:
        out = out.replace("{" + n + "}", _text(args[n]))
    return out


def _text(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return fmt_number(value)
    return str(value)


def _path_children(builder: str, resolved: Mapping[str, Any]) -> tuple[RawNode, ...]:
    points = cast("list[Any]", resolved["points"])
    nodes: list[RawNode] = []
    for entry in points:
        if builder == "bezier_path":
            nodes.append(RawNode("pathPoint", (("pSpline", str(entry)),)))
            continue
        e = cast(Mapping[str, Any], entry)
        attrs: list[tuple[str, str]] = []
        for key in ("angle1", "angle2", "length1", "length2"):
            if key in e:
                attrs.append((key, _text(e[key])))
        attrs.append(("pSpline", str(e["point"])))
        nodes.append(RawNode("pathPoint", tuple(attrs)))
    return tuple(nodes)
