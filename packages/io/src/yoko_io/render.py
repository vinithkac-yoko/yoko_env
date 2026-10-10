"""SVG and PNG rendering of an evaluated pattern.

Display rules (docs/adr/0003-display-rule.md): draw everything Seamly2D draws, every group on, in
one style. Colours, pen styles and weights are ignored; `lineType="none"` means the tool draws no
line at all, so none is drawn (the point still is). Nothing is invented: a line appears only where
a Seamly2D tool draws one.

Coordinates are millimetres, y growing downward (Seamly2D's convention), so the image is what
Seamly2D shows on screen.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont
from yoko_engine.evaluator import CurveGeom, Evaluation
from yoko_engine.model import Obj, Pattern
from yoko_engine.units import px_to_mm

# For point tools that draw a connecting line: the attribute naming the point the line starts from
# (Seamly2D's VToolLinePoint main line and DoubleLinePointTool lines).
_LINE_FROM: dict[str, tuple[str, ...]] = {
    "endLine": ("basePoint",),
    "alongLine": ("firstPoint",),
    "normal": ("firstPoint",),
    "bisector": ("secondPoint",),
    "lineIntersectAxis": ("basePoint",),
    "curveIntersectAxis": ("basePoint",),
    "intersectXY": ("firstPoint", "secondPoint"),
}

POINT_RADIUS_MM = 0.9
STROKE_MM = 0.35
FONT_MM = 3.2


def _mm(p: tuple[float, float]) -> tuple[float, float]:
    return px_to_mm(p[0]), px_to_mm(p[1])


def _hidden(o: Obj) -> bool:
    return (o.get("lineType") or o.get("penStyle")) == "none"


def _curve_polyline(curve: CurveGeom) -> list[tuple[float, float]]:
    geom = curve.geom
    pts = geom.points()
    return [_mm((p.x, p.y)) for p in pts]


@dataclass(frozen=True, slots=True)
class Scene:
    """What to draw, in millimetres, plus the view box."""

    lines: list[tuple[tuple[float, float], tuple[float, float]]]
    polylines: list[list[tuple[float, float]]]
    points: list[tuple[int, str, tuple[float, float]]]
    min_x: float
    min_y: float
    w: float
    h: float


def build_scene(pattern: Pattern, ev: Evaluation, focus_ids: set[int] | None = None) -> Scene:
    """Collect everything Seamly2D draws. `focus_ids` zooms the view onto those objects (the rest
    is still drawn)."""
    lines: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for o in pattern.objects():
        if _hidden(o):
            continue
        if o.tag == "line":
            a = ev.points.get(int(o.get("firstPoint", "-1") or -1))
            b = ev.points.get(int(o.get("secondPoint", "-1") or -1))
            if a and b:
                lines.append((_mm((a.p.x, a.p.y)), _mm((b.p.x, b.p.y))))
        elif o.tag == "point" and o.kind in _LINE_FROM:
            end = ev.points.get(o.id)
            if end is None:
                continue
            for attr in _LINE_FROM[o.kind]:
                start = ev.points.get(int(o.get(attr, "-1") or -1))
                if start:
                    lines.append((_mm((start.p.x, start.p.y)), _mm((end.p.x, end.p.y))))

    polylines: list[list[tuple[float, float]]] = []
    objs = {o.id: o for o in pattern.objects()}
    for cid, curve in ev.curves.items():
        src = objs.get(cid)
        if src is not None and _hidden(src):
            continue
        polylines.append(_curve_polyline(curve))

    points = [(g.id, g.label, _mm((g.p.x, g.p.y))) for g in ev.points.values()]

    focus = set(focus_ids or ())
    xs: list[float] = []
    ys: list[float] = []
    for pid, _label, (x, y) in points:
        if not focus or pid in focus:
            xs.append(x)
            ys.append(y)
    if focus:
        for cid in focus:
            if cid in ev.curves:
                for x, y in _curve_polyline(ev.curves[cid]):
                    xs.append(x)
                    ys.append(y)
    if not xs:
        xs, ys = [0.0, 100.0], [0.0, 100.0]
    margin = 12.0
    min_x, max_x = min(xs) - margin, max(xs) + margin
    min_y, max_y = min(ys) - margin, max(ys) + margin
    return Scene(lines, polylines, points, min_x, min_y, max_x - min_x, max_y - min_y)


def _height_px(scene: Scene, width_px: int) -> int:
    return max(1, round(width_px * scene.h / scene.w)) if scene.w > 0 else width_px


def render_svg(
    pattern: Pattern,
    ev: Evaluation,
    *,
    labels: bool = True,
    focus_ids: set[int] | None = None,
    width_px: int = 1000,
) -> str:
    """The pattern as an SVG document."""
    sc = build_scene(pattern, ev, focus_ids)
    min_x, min_y, w, h = sc.min_x, sc.min_y, sc.w, sc.h
    height_px = _height_px(sc, width_px)

    out: list[str] = [
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="{min_x:.3f} {min_y:.3f} {w:.3f} {h:.3f}" '
        f'width="{width_px}" height="{height_px}">',
        f'<rect x="{min_x:.3f}" y="{min_y:.3f}" width="{w:.3f}" height="{h:.3f}" fill="#ffffff"/>',
        f'<g fill="none" stroke="#1f2933" stroke-width="{STROKE_MM}" stroke-linecap="round" '
        'stroke-linejoin="round" vector-effect="non-scaling-stroke">',
    ]
    for (x1, y1), (x2, y2) in sc.lines:
        out.append(f'<line x1="{x1:.3f}" y1="{y1:.3f}" x2="{x2:.3f}" y2="{y2:.3f}"/>')
    for poly in sc.polylines:
        if len(poly) >= 2:
            d = " ".join(f"{x:.3f},{y:.3f}" for x, y in poly)
            out.append(f'<polyline points="{d}"/>')
    out.append("</g>")
    out.append('<g fill="#1f2933" stroke="none">')
    for _pid, _label, (x, y) in sc.points:
        out.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="{POINT_RADIUS_MM}"/>')
    out.append("</g>")
    if labels:
        out.append(f'<g fill="#52606d" font-family="sans-serif" font-size="{FONT_MM}">')
        for _pid, label, (x, y) in sc.points:
            if label:
                out.append(f'<text x="{x + 1.4:.3f}" y="{y - 1.4:.3f}">{escape(label)}</text>')
        out.append("</g>")
    out.append("</svg>")
    return "\n".join(out)


_SUPERSAMPLE = 2  # draw at twice the size and shrink: smooth lines without a vector rasteriser


def render_png(
    pattern: Pattern,
    ev: Evaluation,
    *,
    labels: bool = True,
    focus_ids: set[int] | None = None,
    width_px: int = 1000,
) -> bytes:
    """The same drawing as `render_svg`, as PNG bytes (for model observations and the studio).

    Drawn with Pillow, so it needs no system libraries or fonts. The output is deterministic for a
    given Pillow version.
    """
    sc = build_scene(pattern, ev, focus_ids)
    width = max(1, width_px)
    height = _height_px(sc, width)
    big_w, big_h = width * _SUPERSAMPLE, height * _SUPERSAMPLE
    scale = big_w / sc.w if sc.w > 0 else 1.0

    def px(p: tuple[float, float]) -> tuple[float, float]:
        return (p[0] - sc.min_x) * scale, (p[1] - sc.min_y) * scale

    ink, grey = (31, 41, 51), (82, 96, 109)
    img = Image.new("RGB", (big_w, big_h), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    stroke = max(1, round(1.2 * _SUPERSAMPLE))
    for a, b in sc.lines:
        draw.line([px(a), px(b)], fill=ink, width=stroke)
    for poly in sc.polylines:
        if len(poly) >= 2:
            draw.line([px(p) for p in poly], fill=ink, width=stroke, joint="curve")
    r = POINT_RADIUS_MM * scale
    for _pid, _label, p in sc.points:
        x, y = px(p)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=ink)
    if labels:
        font = ImageFont.load_default(size=max(8, round(FONT_MM * scale)))
        for _pid, label, p in sc.points:
            if label:
                x, y = px((p[0] + 1.4, p[1] - 1.4))
                draw.text((x, y), label, fill=grey, font=font, anchor="ls")
    img = img.resize((width, height), Image.Resampling.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="PNG", optimize=False)
    return buf.getvalue()
