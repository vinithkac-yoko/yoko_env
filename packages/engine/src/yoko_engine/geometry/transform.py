"""`QTransform`, as far as Seamly2D's operation tools use it (flip, and later rotate and move).

Qt keeps a "type" for the matrix (identity, translate, scale, rotate, shear, project) and takes a
different arithmetic path for each. The paths give the same maths but not the same last bits, so the
type tracking is reproduced too. Verified against real Qt by tests/test_qt_transform.py.
"""

from __future__ import annotations

import math

from yoko_engine.fuzzy import fuzzy_is_null
from yoko_engine.geometry.qt import Line, Pt

# TransformationType
_NONE, _TRANSLATE, _SCALE, _ROTATE, _SHEAR, _PROJECT = range(6)

_DEG2RAD = 0.017453292519943295769  # pi / 180, as written in qtransform.cpp


class Transform:
    """A 3x3 affine transform in Qt's row-vector convention."""

    __slots__ = ("_dirty", "_type", "m11", "m12", "m13", "m21", "m22", "m23", "m33", "m_dx", "m_dy")

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.m11 = 1.0
        self.m12 = 0.0
        self.m13 = 0.0
        self.m21 = 0.0
        self.m22 = 1.0
        self.m23 = 0.0
        self.m_dx = 0.0
        self.m_dy = 0.0
        self.m33 = 1.0
        self._type = _NONE
        self._dirty = _NONE

    # -- type tracking (QTransform::type) -------------------------------------------------------
    def _inline_type(self) -> int:
        if self._dirty == _NONE or self._dirty < self._type:
            return self._type
        return self._compute_type()

    def _compute_type(self) -> int:
        t = self._dirty
        result = _NONE
        if t == _PROJECT:
            if (
                not fuzzy_is_null(self.m13)
                or not fuzzy_is_null(self.m23)
                or not fuzzy_is_null(self.m33 - 1)
            ):
                self._type = _PROJECT
                self._dirty = _NONE
                return self._type
            t = _SHEAR
        if t in (_SHEAR, _ROTATE):
            if not fuzzy_is_null(self.m12) or not fuzzy_is_null(self.m21):
                dot = self.m11 * self.m12 + self.m21 * self.m22
                self._type = _ROTATE if fuzzy_is_null(dot) else _SHEAR
                self._dirty = _NONE
                return self._type
            t = _SCALE
        if t == _SCALE:
            if not fuzzy_is_null(self.m11 - 1) or not fuzzy_is_null(self.m22 - 1):
                self._type = _SCALE
                self._dirty = _NONE
                return self._type
            t = _TRANSLATE
        if t == _TRANSLATE and (not fuzzy_is_null(self.m_dx) or not fuzzy_is_null(self.m_dy)):
            self._type = _TRANSLATE
            self._dirty = _NONE
            return self._type
        self._type = result
        self._dirty = _NONE
        return self._type

    # -- operations -------------------------------------------------------------------------------
    def translate(self, dx: float, dy: float) -> Transform:
        if dx == 0 and dy == 0:
            return self
        t = self._inline_type()
        if t == _NONE:
            self.m_dx = dx
            self.m_dy = dy
        elif t == _TRANSLATE:
            self.m_dx += dx
            self.m_dy += dy
        elif t == _SCALE:
            self.m_dx += dx * self.m11
            self.m_dy += dy * self.m22
        else:
            if t == _PROJECT:
                self.m33 += dx * self.m13 + dy * self.m23
            self.m_dx += dx * self.m11 + dy * self.m21
            self.m_dy += dy * self.m22 + dx * self.m12
        if self._dirty < _TRANSLATE:
            self._dirty = _TRANSLATE
        return self

    def scale(self, sx: float, sy: float) -> Transform:
        if sx == 1 and sy == 1:
            return self
        t = self._inline_type()
        if t in (_NONE, _TRANSLATE):
            self.m11 = sx
            self.m22 = sy
        else:
            if t == _PROJECT:
                self.m13 *= sx
                self.m23 *= sy
            if t in (_PROJECT, _ROTATE, _SHEAR):
                self.m12 *= sx
                self.m21 *= sy
            self.m11 *= sx
            self.m22 *= sy
        if self._dirty < _SCALE:
            self._dirty = _SCALE
        return self

    def rotate(self, a: float) -> Transform:
        """Rotate about the origin by `a` degrees (QTransform::rotate, Z axis)."""
        if a == 0:
            return self
        sina = 0.0
        cosa = 0.0
        if a in (90.0, -270.0):
            sina = 1.0
        elif a in (270.0, -90.0):
            sina = -1.0
        elif a == 180.0:
            cosa = -1.0
        else:
            b = _DEG2RAD * a
            sina = math.sin(b)
            cosa = math.cos(b)
        t = self._inline_type()
        if t in (_NONE, _TRANSLATE):
            self.m11 = cosa
            self.m12 = sina
            self.m21 = -sina
            self.m22 = cosa
        elif t == _SCALE:
            tm11 = cosa * self.m11
            tm12 = sina * self.m22
            tm21 = -sina * self.m11
            tm22 = cosa * self.m22
            self.m11, self.m12, self.m21, self.m22 = tm11, tm12, tm21, tm22
        else:
            if t == _PROJECT:
                tm13 = cosa * self.m13 + sina * self.m23
                tm23 = -sina * self.m13 + cosa * self.m23
                self.m13, self.m23 = tm13, tm23
            tm11 = cosa * self.m11 + sina * self.m21
            tm12 = cosa * self.m12 + sina * self.m22
            tm21 = -sina * self.m11 + cosa * self.m21
            tm22 = -sina * self.m12 + cosa * self.m22
            self.m11, self.m12, self.m21, self.m22 = tm11, tm12, tm21, tm22
        if self._dirty < _ROTATE:
            self._dirty = _ROTATE
        return self

    def multiply(self, o: Transform) -> Transform:
        """`*=`: this = this * o (apply this first, then o)."""
        other_type = o._inline_type()
        if other_type == _NONE:
            return self
        this_type = self._inline_type()
        if this_type == _NONE:
            self.m11, self.m12, self.m13 = o.m11, o.m12, o.m13
            self.m21, self.m22, self.m23 = o.m21, o.m22, o.m23
            self.m_dx, self.m_dy, self.m33 = o.m_dx, o.m_dy, o.m33
            self._type = o._type
            self._dirty = o._dirty
            return self
        t = max(this_type, other_type)
        if t == _TRANSLATE:
            self.m_dx += o.m_dx
            self.m_dy += o.m_dy
        elif t == _SCALE:
            m11 = self.m11 * o.m11
            m22 = self.m22 * o.m22
            m31 = self.m_dx * o.m11 + o.m_dx
            m32 = self.m_dy * o.m22 + o.m_dy
            self.m11, self.m22, self.m_dx, self.m_dy = m11, m22, m31, m32
        elif t in (_ROTATE, _SHEAR):
            m11 = self.m11 * o.m11 + self.m12 * o.m21
            m12 = self.m11 * o.m12 + self.m12 * o.m22
            m21 = self.m21 * o.m11 + self.m22 * o.m21
            m22 = self.m21 * o.m12 + self.m22 * o.m22
            m31 = self.m_dx * o.m11 + self.m_dy * o.m21 + o.m_dx
            m32 = self.m_dx * o.m12 + self.m_dy * o.m22 + o.m_dy
            self.m11, self.m12, self.m21, self.m22 = m11, m12, m21, m22
            self.m_dx, self.m_dy = m31, m32
        else:
            raise NotImplementedError("projective transforms are not used by Seamly2D")
        self._dirty = t
        self._type = t
        return self

    def map(self, p: Pt) -> Pt:
        t = self._inline_type()
        x, y = p.x, p.y
        if t == _NONE:
            return Pt(x, y)
        if t == _TRANSLATE:
            return Pt(x + self.m_dx, y + self.m_dy)
        if t == _SCALE:
            return Pt(self.m11 * x + self.m_dx, self.m22 * y + self.m_dy)
        nx = self.m11 * x + self.m21 * y + self.m_dx
        ny = self.m12 * x + self.m22 * y + self.m_dy
        if t == _PROJECT:
            w = 1.0 / (self.m13 * x + self.m23 * y + self.m33)
            return Pt(nx * w, ny * w)
        return Pt(nx, ny)


def flip_transform(axis: Line) -> Transform:
    """VGObject::flipTransform: reflection across the (infinite) line through `axis`."""
    transform = Transform()
    if axis.is_null():
        return transform
    axis_ox = Line(axis.p2, Pt(axis.p2.x + 100, axis.p2.y))
    angle = axis.angle_to(axis_ox)
    p2 = axis.p2

    m = Transform()
    m.translate(p2.x, p2.y)
    m.rotate(-angle)
    m.translate(-p2.x, -p2.y)
    transform.multiply(m)

    m.reset()
    m.translate(p2.x, p2.y)
    m.scale(m.m11, m.m22 * -1)
    m.translate(-p2.x, -p2.y)
    transform.multiply(m)

    m.reset()
    m.translate(p2.x, p2.y)
    m.rotate(-(360 - angle))
    m.translate(-p2.x, -p2.y)
    transform.multiply(m)
    return transform


def flip_point(axis: Line, point: Pt) -> Pt:
    """VPointF::FlipPF."""
    return flip_transform(axis).map(point)
