"""Pieces: the outline of each piece of a pattern.

A piece lists nodes (`<node idObject=.. type=NodePoint|NodeSpline|..>`) that refer to *modeling*
objects: copies of draft points and curves kept in the `<modeling>` section. The outline is the
points of the nodes in order; a curve node contributes the part of the curve between its
neighbouring points (`VPiecePath::PathPoints`), and the whole is cleaned like Seamly2D's main path
(`VPiece::mainPathPoints`). Seam allowance, grainline, notches, labels and internal paths are kept
unchanged but not computed.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from yoko_engine.evalcore import CurveGeom, Evaluation
from yoko_engine.geometry.outline import (
    check_loops,
    correct_equidistant_points,
    is_point_on_curve,
    segment_points,
)
from yoko_engine.geometry.qt import Pt
from yoko_engine.model import Pattern, RawNode
from yoko_engine.union import Child, UnionError, parse_union, unite

NODE_POINT = "NodePoint"
CURVE_NODES = frozenset({"NodeArc", "NodeElArc", "NodeSpline", "NodeSplinePath"})


@dataclass(frozen=True, slots=True)
class PieceNode:
    id: int  # the modeling object it refers to
    type: str
    reverse: bool = False
    excluded: bool = False


@dataclass(frozen=True, slots=True)
class PieceGeom:
    id: int
    name: str
    outline: tuple[Pt, ...]
    nodes: tuple[PieceNode, ...] = ()
    problems: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Modeling:
    """The copies the `<modeling>` section makes: points by id, curves by id (not drawn)."""

    points: dict[int, tuple[str, Pt]]
    curves: dict[int, CurveGeom]
    problems: tuple[str, ...] = ()


def _truthy(raw: str | None) -> bool:
    return (raw or "").lower() in ("1", "true")


def _int(raw: str | None) -> int | None:
    return int(raw) if raw is not None and raw.isdigit() else None


def modeling_objects(sections: tuple[RawNode, ...], ev: Evaluation) -> Modeling:
    """Seamly2D's `ParseNode*`: each modeling object copies the geometry of the draft object it
    names in `idObject`. A copy of something that no longer exists is ignored. A union tool
    (`<tools type="union">`) makes objects of its own (the second piece moved onto the first);
    copies that name one of those take the moved geometry."""
    points: dict[int, tuple[str, Pt]] = {}
    curves: dict[int, CurveGeom] = {}
    made: dict[int, Child] = {}
    problems: list[str] = []
    for section in sections:
        if section.tag != "modeling":
            continue
        for node in section.children:
            union = parse_union(node)
            if union is not None:
                try:
                    made.update(unite(union, points, curves))
                except UnionError as e:
                    problems.append(f"union {union.tool_id}: {e}")
                continue
            mid, source = _int(node.get("id")), _int(node.get("idObject"))
            if mid is None or source is None:
                continue
            if source in made:
                child = made[source]
                if child.point is not None and node.tag == "point":
                    points[mid] = child.point
                elif child.curve is not None and node.tag != "point":
                    c = child.curve
                    curves[mid] = CurveGeom(mid, c.name, c.geom, c.labels, drawn=False)
            elif source in ev.points and node.tag == "point":
                p = ev.points[source]
                points[mid] = (p.label, p.p)
            elif source in ev.curves:
                src = ev.curves[source]
                curves[mid] = CurveGeom(mid, src.name, src.geom, src.labels, drawn=False)
    return Modeling(points, curves, tuple(problems))


def piece_nodes(piece: RawNode) -> tuple[PieceNode, ...]:
    out: list[PieceNode] = []
    for child in piece.children:
        if child.tag != "nodes":
            continue
        for node in child.children:
            nid = _int(node.get("idObject"))
            if node.tag != "node" or nid is None:
                continue
            out.append(
                PieceNode(
                    nid,
                    node.get("type", "") or "",
                    reverse=_truthy(node.get("reverse")),
                    excluded=_truthy(node.get("excluded")),
                )
            )
    return tuple(out)


def _neighbour(nodes: tuple[PieceNode, ...], start: int, step: int) -> int:
    """FindInLoopNotExcludedUp/Down: the nearest node not excluded, going round the loop."""
    n = len(nodes)
    if not 0 <= start < n:
        return -1
    i = (n - 1 if start == 0 else start - 1) if step < 0 else (0 if start == n - 1 else start + 1)
    for _ in range(n):
        if not nodes[i].excluded:
            return i
        i = (i + step) % n
    return -1


class _Outline:
    def __init__(self, nodes: tuple[PieceNode, ...], modeling: Modeling) -> None:
        self.nodes = nodes
        self.m = modeling

    def _curve_points(self, node: PieceNode) -> list[Pt]:
        return self.m.curves[node.id].geom.points()

    def _curve_start(self, candidate: Pt, node: PieceNode, curve_points: list[Pt]) -> Pt:
        """CurveStartPoint: the previous node may pull the segment's start onto itself."""
        if node.type == NODE_POINT:
            return self._curve_point(candidate, node, curve_points)
        points = self._curve_points(node)
        if points:
            end = points[0] if node.reverse else points[-1]
            if is_point_on_curve(curve_points, end):
                return end
        return candidate

    def _curve_end(self, candidate: Pt, node: PieceNode, curve_points: list[Pt]) -> Pt:
        if node.type == NODE_POINT:
            return self._curve_point(candidate, node, curve_points)
        points = self._curve_points(node)
        if points:
            begin = points[-1] if node.reverse else points[0]
            if is_point_on_curve(curve_points, begin):
                return begin
        return candidate

    def _curve_point(self, candidate: Pt, node: PieceNode, curve_points: list[Pt]) -> Pt:
        p = self.m.points[node.id][1]
        return p if is_point_on_curve(curve_points, p) else candidate

    def start_segment(self, i: int, reverse: bool) -> Pt | None:
        points = self._curve_points(self.nodes[i])
        if not points:
            return None
        begin = points[-1] if reverse else points[0]
        if len(self.nodes) > 1:
            index = _neighbour(self.nodes, i, -1)
            if index not in (i, -1):
                begin = self._curve_start(begin, self.nodes[index], points)
        return begin

    def end_segment(self, i: int, reverse: bool) -> Pt | None:
        points = self._curve_points(self.nodes[i])
        if not points:
            return None
        end = points[0] if reverse else points[-1]
        if len(self.nodes) > 2:
            index = _neighbour(self.nodes, i, +1)
            if index not in (i, -1):
                end = self._curve_end(end, self.nodes[index], points)
        return end

    def contributions(self) -> list[tuple[int, list[Pt]]]:
        """For each node that is not excluded, its index and the points it adds to the path."""
        out: list[tuple[int, list[Pt]]] = []
        for i, node in enumerate(self.nodes):
            if node.excluded:
                continue
            if node.type == NODE_POINT:
                out.append((i, [self.m.points[node.id][1]]))
            elif node.type in CURVE_NODES:
                begin = self.start_segment(i, node.reverse)
                end = self.end_segment(i, node.reverse)
                if begin is None or end is None:
                    continue
                out.append((i, segment_points(self._curve_points(node), begin, end, node.reverse)))
        return out

    def path_points(self) -> list[Pt]:
        return [p for _, pts in self.contributions() for p in pts]


def piece_outline(nodes: tuple[PieceNode, ...], modeling: Modeling) -> tuple[Pt, ...]:
    """The cleaned main path of a piece (`VPiece::mainPathPoints`)."""
    points = _Outline(nodes, modeling).path_points()
    return tuple(check_loops(correct_equidistant_points(points)))


def node_marks(nodes: tuple[PieceNode, ...], modeling: Modeling) -> list[tuple[int, Pt]]:
    """One spot per node, in outline order: the point itself, or the middle of a curve's part of
    the outline. For labelling a drawing of the piece."""
    marks: list[tuple[int, Pt]] = []
    for index, pts in _Outline(nodes, modeling).contributions():
        if pts:
            marks.append((index, pts[len(pts) // 2]))
    return marks


def evaluate_pieces(pattern: Pattern, ev: Evaluation) -> Mapping[int, PieceGeom]:
    """The outline of every piece in the pattern. A piece that refers to something missing gets an
    empty outline and the reason in `problems` instead of failing the whole pattern."""
    result: dict[int, PieceGeom] = {}
    for block in pattern.blocks:
        modeling = modeling_objects(block.sections, ev)
        for section in block.sections:
            if section.tag != "pieces":
                continue
            for piece in section.children:
                pid = _int(piece.get("id"))
                if piece.tag != "piece" or pid is None:
                    continue
                nodes = piece_nodes(piece)
                name = piece.get("name", "") or ""
                missing = _missing(nodes, modeling)
                if missing:
                    result[pid] = PieceGeom(pid, name, (), nodes, (*modeling.problems, *missing))
                else:
                    result[pid] = PieceGeom(pid, name, piece_outline(nodes, modeling), nodes)
    return result


def _missing(nodes: tuple[PieceNode, ...], modeling: Modeling) -> tuple[str, ...]:
    problems: list[str] = []
    for node in nodes:
        if node.type == NODE_POINT and node.id not in modeling.points:
            problems.append(f"node {node.id}: no such point")
        elif node.type in CURVE_NODES and node.id not in modeling.curves:
            problems.append(f"node {node.id}: no such curve")
        elif node.type != NODE_POINT and node.type not in CURVE_NODES:
            problems.append(f"node {node.id}: unknown type {node.type!r}")
    return tuple(problems)
