"""Union of two pieces: join them along one edge each.

Ported from `UnionTool` (src/libs/vtools/tools/union_tool.cpp), the path Seamly2D takes when it
reads a saved union (`updateUnion`). The file holds the ids of the objects the tool made
(`children`); the tool moves the second piece so that its chosen edge lies on the first piece's
chosen edge, and those objects get the moved geometry. Pieces that refer to them (`modeling` points
and curves whose `idObject` is a child id) then read it from there.

Only the main outline is united. Seam allowance paths, internal paths and anchors of the two pieces
are left alone, not computed.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from yoko_engine.evalcore import CurveGeom
from yoko_engine.fuzzy import fuzzy_compare_possible_nulls
from yoko_engine.geometry.curves import (
    Arc,
    Bezier,
    BezierPath,
    Spline,
    SplinePath,
    SplinePoint,
)
from yoko_engine.geometry.qt import Line, Pt
from yoko_engine.model import RawNode

NODE_POINT = "NodePoint"


class UnionError(ValueError):
    """The union cannot be computed (something it needs is missing or not supported)."""


@dataclass(frozen=True, slots=True)
class UNode:
    id: int
    type: str
    reverse: bool = False


@dataclass(frozen=True, slots=True)
class UnionData:
    """What a `<tools type="union">` element says."""

    tool_id: int
    index1: int
    index2: int
    path1: tuple[UNode, ...]
    path2: tuple[UNode, ...]
    children: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class Child:
    """One object the union made: a point (label, position) or a curve."""

    point: tuple[str, Pt] | None = None
    curve: CurveGeom | None = None


def _int(raw: str | None) -> int | None:
    return int(raw) if raw is not None and raw.isdigit() else None


def parse_union(node: RawNode) -> UnionData | None:
    """Read a union tool element; None when it is not one or lacks what it needs."""
    tool_id, i1, i2 = _int(node.get("id")), _int(node.get("indexD1")), _int(node.get("indexD2"))
    if node.tag != "tools" or node.get("type") != "union" or None in (tool_id, i1, i2):
        return None
    paths: list[tuple[UNode, ...]] = []
    children: list[int] = []
    for part in node.children:
        if part.tag == "unionPiece":
            nodes: list[UNode] = []
            for group in part.children:
                if group.tag != "nodes":
                    continue
                for n in group.children:
                    nid = _int(n.get("idObject"))
                    if n.tag == "node" and nid is not None:
                        rev = (n.get("reverse") or "").lower() in ("1", "true")
                        nodes.append(UNode(nid, n.get("type", "") or "", rev))
            paths.append(tuple(nodes))
        elif part.tag == "children":
            for group in part.children:
                # the first <nodes> group is the main outline's; others hold paths and anchors
                if group.tag == "nodes":
                    children.extend(c for ch in group.children if (c := _int(ch.text)) is not None)
                    break
    if len(paths) != 2 or tool_id is None or i1 is None or i2 is None:
        return None
    return UnionData(tool_id, i1, i2, paths[0], paths[1], tuple(children))


# -- paths (VPiecePath) --------------------------------------------------------------------------
def _index_of(path: tuple[UNode, ...], node_id: int) -> int:
    for i, n in enumerate(path):
        if n.id == node_id:
            return i
    return -1


def node_on_edge(path: tuple[UNode, ...], index: int) -> tuple[UNode, UNode]:
    """VPiecePath::NodeOnEdge: the two point nodes an edge runs between."""
    points = [n for n in path if n.type == NODE_POINT]
    if index >= len(points):
        raise UnionError(f"edge {index} does not exist")
    return points[index], points[index + 1 if index + 1 < len(points) else 0]


def remove_edge(path: tuple[UNode, ...], index: int) -> tuple[UNode, ...]:
    """VPiecePath::RemoveEdge: the path without the nodes inside edge `index` (the curves along it);
    the edge's own two points stay."""
    out: list[UNode] = []
    edges = sum(1 for n in path if n.type == NODE_POINT)
    k = 0
    for i in range(edges):
        if i == index:
            out.append(path[k])
            k += 1
        else:
            p1, p2 = node_on_edge(path, i)
            j1 = _index_of(path, p1.id)
            j2 = _index_of(path, p2.id)
            if j2 == 0:
                j2 = len(path)
            for j in range(j1, j2):
                out.append(path[j])
                k += 1
    return tuple(out)


# -- moving geometry (BiasRotatePoint) ------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Move:
    dx: float
    dy: float
    pivot: Pt
    angle: float

    def apply(self, p: Pt) -> Pt:
        line = Line(self.pivot, Pt(p.x + self.dx, p.y + self.dy))
        return line.set_angle(line.angle() + self.angle).p2


def _identity(p: Pt) -> Pt:
    return p


Mover = Callable[[Pt], Pt]


def _spline_corners(geom: object) -> tuple[Pt, Pt, Pt, Pt]:
    if isinstance(geom, Spline):
        return geom.p1, geom.c1, geom.c2, geom.p4
    if isinstance(geom, Bezier):
        return geom.p1, geom.c1, geom.c2, geom.p4
    raise UnionError("this curve is not a spline")


def _moved_spline(geom: object, move: Mover) -> Spline:
    p1, p2, p3, p4 = _spline_corners(geom)
    return Spline.from_points(move(p1), move(p2), move(p3), move(p4))


def _moved_arc(arc: Arc, move: Mover) -> Arc:
    if arc.flipped:
        raise UnionError("a mirrored arc cannot be united yet")
    center = move(arc.center)
    start = Line(center, move(arc.p1()))
    end = Line(center, move(arc.p2()))
    return Arc(center, arc.radius, start.angle(), end.angle())


def _moved_path(geom: object, move: Mover, label: str) -> SplinePath:
    if not isinstance(geom, BezierPath | SplinePath):
        raise UnionError("this curve is not a spline path")
    segments = geom.segments()
    path = SplinePath(())
    count = len(segments)
    for i, seg in enumerate(segments):
        p1, p2, p3, p4 = move(seg.p1), move(seg.c1), move(seg.c2), move(seg.p4)
        spl = Spline.from_points(p1, p2, p3, p4)
        if i == 0:
            path = path.append(_point(p1, label, spl.angle1 + 180, spl.angle1, 0.0, seg.c1_len))
        length2 = segments[i + 1].c1_len if i + 1 < count else 0.0
        path = path.append(_point(p4, label, spl.angle2, spl.angle2 + 180, seg.c2_len, length2))
    return path


def _point(p: Pt, label: str, a1: float, a2: float, l1: float, l2: float) -> SplinePoint:
    """VSplinePointData with both angles given as plain numbers: kept as given when they are
    opposite, otherwise angle2 follows angle1."""
    if not fuzzy_compare_possible_nulls(abs(a1 - a2), 180):
        a2 = Line(Pt(0.0, 0.0), Pt(100.0, 0.0)).set_angle(a1 + 180).angle()
    return SplinePoint(p, label, a1, a2, l1, l2)


# -- the tool -------------------------------------------------------------------------------------
def _copy(
    node: UNode,
    points: Mapping[int, tuple[str, Pt]],
    curves: Mapping[int, CurveGeom],
    move: Mover,
) -> Child:
    if node.type == NODE_POINT:
        if node.id not in points:
            raise UnionError(f"node {node.id}: no such point")
        label, p = points[node.id]
        return Child(point=(label, move(p)))
    src = curves.get(node.id)
    if src is None:
        raise UnionError(f"node {node.id}: no such curve")
    if node.type == "NodeArc":
        if not isinstance(src.geom, Arc):
            raise UnionError(f"node {node.id}: not an arc")
        geom: Arc | Spline | SplinePath = _moved_arc(src.geom, move)
    elif node.type == "NodeSpline":
        geom = _moved_spline(src.geom, move)
    elif node.type == "NodeSplinePath":
        geom = _moved_path(src.geom, move, src.name)
    else:
        raise UnionError(f"node {node.id}: {node.type} cannot be united yet")
    return Child(curve=CurveGeom(src.id, src.name, geom, src.labels, drawn=False))


def unite(
    data: UnionData,
    points: Mapping[int, tuple[str, Pt]],
    curves: Mapping[int, CurveGeom],
) -> dict[int, Child]:
    """`UnionTool::updateUnion` for the main outline: the objects whose ids the file lists as the
    tool's children. Raises `UnionError` when something is missing or the file disagrees."""
    first, _ = node_on_edge(data.path1, data.index1)
    p1_id, p2_id = (n.id for n in node_on_edge(data.path1, data.index1))
    p3_id, p4_id = (n.id for n in node_on_edge(data.path2, data.index2))
    for needed in (p1_id, p2_id, p3_id, p4_id):
        if needed not in points:
            raise UnionError(f"edge point {needed}: no such point")
    point1, point2 = points[p1_id][1], points[p2_id][1]
    point3, point4 = points[p3_id][1], points[p4_id][1]
    dx = point1.x - point4.x
    dy = point1.y - point4.y
    shifted3 = Pt(point3.x + dx, point3.y + dy)
    shifted4 = Pt(point4.x + dx, point4.y + dy)
    angle = Line(shifted4, shifted3).angle_to(Line(point1, point2))
    pivot_id = first.id
    move = Move(dx, dy, points[pivot_id][1], angle).apply

    re1 = remove_edge(data.path1, data.index1)
    re2 = remove_edge(data.path2, data.index2)
    count1, count2 = len(re1), len(re2)
    if len(data.children) != count1 + count2 - 1:
        raise UnionError(
            f"the union lists {len(data.children)} objects, expected {count1 + count2 - 1}"
        )
    children = list(data.children)
    out: dict[int, Child] = {}

    def take(node: UNode, mover: Mover) -> None:
        out[children.pop(0)] = _copy(node, points, curves, mover)

    done2 = 0
    i = 0
    pivot_index = _index_of(data.path1, pivot_id)
    while True:
        take(re1[i], _identity)
        i += 1
        if i > pivot_index and done2 < count2 - 1:
            j = 0
            if done2 == 0:
                _, node2 = node_on_edge(data.path2, data.index2)
                k = _index_of(re2, node2.id)
                if k == -1:
                    raise UnionError("the second piece's edge is not in its outline")
                j = 0 if k == count2 - 1 else k + 1
            while True:
                if j >= count2:
                    j = 0
                take(re2[j], move)
                done2 += 1
                j += 1
                if done2 >= count2 - 1:
                    break
        if i >= count1:
            break
    return out
