"""Evaluate a pattern: run the construction graph in order and compute geometry.

This mirrors how Seamly2D loads a file (src/app/seamly2d/xml/vpattern.cpp): measurements first, then
variables in file order, then every draft block's objects in file order. Each object is built from
earlier objects plus formulas; a formula sees measurements, variables, and the geometric variables
(`Line_A_B`, `AngleLine_A_B`, ...) that earlier objects registered.

Geometry is computed in Seamly2D's native 96-dpi pixel scale with its exact arithmetic (see
`yoko_engine.units`); `Evaluation` converts to mm for callers. The per-kind computations live in
`yoko_engine.handlers`; this module runs them in order, incrementally.
"""

from __future__ import annotations

from collections.abc import Mapping

from yoko_engine.evalcore import (
    Ctx,
    CurveGeom,
    Evaluation,
    Issue,
    ObjectError,
    ObjRecord,
    PointGeom,
)
from yoko_engine.formula import FormulaError, parse
from yoko_engine.geometry import points_equal
from yoko_engine.handlers import HANDLERS, PENDING_KINDS
from yoko_engine.model import Obj, Pattern, Variable


def kind_key(o: Obj) -> str:
    """Points are keyed by their type; other objects by element and type (so arcs and elliptical
    arcs, both `simple`, stay apart)."""
    return o.kind if o.tag == "point" else f"{o.tag}:{o.kind}"


def _eval_variable(ev: Evaluation, var: Variable) -> Issue | None:
    try:
        ev.symbols[var.name] = parse(var.formula).evaluate(ev.symbols)
    except FormulaError as err:
        ev.symbols[var.name] = 0.0
        return Issue(
            f"formula_{err.code.value}",
            f"variable {var.name}: {err.message}",
            None,
            var.name,
            err.hint,
        )
    return None


class Evaluator:
    """Evaluates a pattern, and re-evaluates it incrementally after a change.

    `run` evaluates everything. `update` takes the changed pattern and recomputes only the objects
    that are edited, new, or built from something whose value actually changed (so a change that
    does not alter a result stops propagating there).
    """

    def __init__(self) -> None:
        self.ev = Evaluation()
        self.records: dict[int, ObjRecord] = {}
        self.var_issues: list[Issue] = []
        self._measurement_names: set[str] = set()
        self._variable_names: set[str] = set()
        self.last_reevaluated = 0

    def copy(self) -> Evaluator:
        other = Evaluator()
        other.ev = self.ev.copy()
        other.records = dict(self.records)
        other.var_issues = list(self.var_issues)
        other._measurement_names = set(self._measurement_names)
        other._variable_names = set(self._variable_names)
        other.last_reevaluated = self.last_reevaluated
        return other

    def run(self, pattern: Pattern, measurements: Mapping[str, float]) -> Evaluation:
        self.__init__()  # type: ignore[misc]
        self.update(pattern, measurements, set())
        return self.ev

    def update(
        self, pattern: Pattern, measurements: Mapping[str, float], edited_ids: set[int]
    ) -> Evaluation:
        ev = self.ev
        changed_names: set[str] = set()
        changed_ids: set[int] = set()

        # measurements
        for name in self._measurement_names - set(measurements):
            ev.symbols.pop(name, None)
            changed_names.add(name)
        for name, value in measurements.items():
            if name not in ev.symbols or ev.symbols[name] != value:
                ev.symbols[name] = value
                changed_names.add(name)
        self._measurement_names = set(measurements)

        # variables, in file order
        for name in self._variable_names - {v.name for v in pattern.variables}:
            ev.symbols.pop(name, None)
            changed_names.add(name)
        self.var_issues = []
        for var in pattern.variables:
            before = ev.symbols.get(var.name)
            issue = _eval_variable(ev, var)
            if issue is not None:
                self.var_issues.append(issue)
            if before is None or ev.symbols[var.name] != before:
                changed_names.add(var.name)
        self._variable_names = {v.name for v in pattern.variables}

        # objects, in file order
        ctx = Ctx(pattern.unit, ev)
        ctx.order = {o.id: i for i, o in enumerate(pattern.objects())}
        present = {o.id for b in pattern.blocks for o in b.objects}
        for oid in [i for i in self.records if i not in present]:
            self._drop(oid, changed_ids, changed_names)
        count = 0
        for block in pattern.blocks:
            for o in block.objects:
                rec = self.records.get(o.id)
                dirty = (
                    rec is None
                    or o.id in edited_ids
                    or not rec.uses_ids.isdisjoint(changed_ids)
                    or not rec.uses_names.isdisjoint(changed_names)
                )
                if not dirty:
                    continue
                count += 1
                ctx.current = ctx.order[o.id]
                self._run_object(ctx, o, changed_ids, changed_names)
        self.last_reevaluated = count

        ev.issues = list(self.var_issues)
        for block in pattern.blocks:
            for o in block.objects:
                ev.issues.extend(self.records[o.id].issues)
        return ev

    # -- internals --------------------------------------------------------------------------
    def _snapshot(
        self, rec: ObjRecord | None
    ) -> tuple[dict[int, PointGeom], dict[int, CurveGeom], dict[str, float]]:
        if rec is None:
            return {}, {}, {}
        ev = self.ev
        return (
            {i: ev.points[i] for i in rec.points if i in ev.points},
            {i: ev.curves[i] for i in rec.curves if i in ev.curves},
            {n: ev.symbols[n] for n in rec.symbols if n in ev.symbols},
        )

    def _remove_outputs(self, oid: int, rec: ObjRecord | None) -> None:
        if rec is None:
            return
        ev = self.ev
        for i in rec.points:
            ev.points.pop(i, None)
        for i in rec.curves:
            ev.curves.pop(i, None)
        for n in rec.symbols:
            if ev.owners.get(n) == oid:
                ev.symbols.pop(n, None)
                ev.owners.pop(n, None)
        ev.deps.pop(oid, None)

    def _drop(self, oid: int, changed_ids: set[int], changed_names: set[str]) -> None:
        rec = self.records.pop(oid, None)
        if rec is None:
            return
        changed_ids.update(rec.points)
        changed_ids.update(rec.curves)
        changed_names.update(rec.symbols)
        self._remove_outputs(oid, rec)

    def _run_object(self, ctx: Ctx, o: Obj, changed_ids: set[int], changed_names: set[str]) -> None:
        old = self.records.get(o.id)
        old_points, old_curves, old_symbols = self._snapshot(old)
        self._remove_outputs(o.id, old)
        rec = ctx.begin()
        key = kind_key(o)
        handler = HANDLERS.get(key)
        if handler is None:
            code = "pending_kind" if key in PENDING_KINDS else "unknown_kind"
            rec.issues.append(
                Issue(code, f"object kind {o.kind!r} is not evaluated yet", o.id, None)
            )
        else:
            try:
                handler(ctx, o)
            except ObjectError as err:
                rec.issues.append(err.issue)
        self.records[o.id] = rec
        self.ev.deps[o.id] = frozenset(rec.uses_ids)
        # what changed, for the objects built from this one
        for pid in old_points.keys() | rec.points:
            new_pt = self.ev.points.get(pid)
            if old_points.get(pid) != new_pt:
                changed_ids.add(pid)
        for cid in old_curves.keys() | rec.curves:
            if old_curves.get(cid) != self.ev.curves.get(cid):
                changed_ids.add(cid)
        for name in old_symbols.keys() | rec.symbols:
            if old_symbols.get(name) != self.ev.symbols.get(name):
                changed_names.add(name)


def evaluate(pattern: Pattern, measurements: Mapping[str, float]) -> Evaluation:
    """Run the whole pattern. Never raises for a bad pattern: problems come back as issues."""
    return Evaluator().run(pattern, measurements)


__all__ = [
    "CurveGeom",
    "Evaluation",
    "Evaluator",
    "Issue",
    "PointGeom",
    "evaluate",
    "points_equal",
]
