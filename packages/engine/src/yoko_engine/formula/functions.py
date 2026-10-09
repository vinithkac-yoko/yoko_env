"""Built-in functions and constants, ported from Seamly2D's `QmuParser`.

Source: src/libs/qmuparser/qmuparser.cpp (`InitFun`, `InitConst`, and the functions above them).
C++ floating point never raises, Python's `math` often does, so every function here maps the
exception back to the IEEE result C++ would return (nan or +/-inf).
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

from yoko_engine.fuzzy import fuzzy_compare, fuzzy_compare_possible_nulls, fuzzy_is_null

__all__ = ["fuzzy_compare", "fuzzy_compare_possible_nulls", "fuzzy_is_null"]

NAN = math.nan
INF = math.inf


def c_div(a: float, b: float) -> float:
    """IEEE division: Seamly2D leaves MUP_MATH_EXCEPTIONS off, so x/0 is inf or nan."""
    if b == 0.0:
        if a == 0.0 or math.isnan(a):
            return NAN
        return math.copysign(INF, a) * math.copysign(1.0, b)
    return a / b


def c_pow(a: float, b: float) -> float:
    """std::pow."""
    try:
        return math.pow(a, b)
    except OverflowError:
        negative = a < 0 and b == math.floor(b) and math.fmod(b, 2.0) != 0.0
        return -INF if negative else INF
    except ValueError:
        if a == 0.0 and b < 0:  # pow(+-0, negative) is +-inf in C
            odd = b == math.floor(b) and math.fmod(b, 2.0) != 0.0
            return math.copysign(INF, a) if odd else INF
        return NAN


def _log(x: float) -> float:
    if math.isnan(x) or x < 0:
        return NAN
    if x == 0:
        return -INF
    return math.log(x)


def _log10(x: float) -> float:
    if math.isnan(x) or x < 0:
        return NAN
    if x == 0:
        return -INF
    return math.log10(x)


def _sqrt(x: float) -> float:
    return math.sqrt(x) if x >= 0 else NAN


def _guard(fn: Callable[[float], float]) -> Callable[[float], float]:
    def wrapped(x: float) -> float:
        try:
            return fn(x)
        except ValueError:
            return NAN
        except OverflowError:
            return INF

    return wrapped


def _sinh(x: float) -> float:
    try:
        return math.sinh(x)
    except OverflowError:
        return math.copysign(INF, x)


def _exp(x: float) -> float:
    try:
        return math.exp(x)
    except OverflowError:
        return INF


def _fmod(a: float, b: float) -> float:
    try:
        return math.fmod(a, b)
    except ValueError:
        return NAN


# Degrees <-> radians exactly as Qt does it (qDegreesToRadians / qRadiansToDegrees).
def deg_to_rad(d: float) -> float:
    return d * (math.pi / 180.0)


def rad_to_deg(r: float) -> float:
    return r * (180.0 / math.pi)


def _asin(x: float) -> float:
    return math.asin(x) if -1.0 <= x <= 1.0 else NAN


def _acos(x: float) -> float:
    return math.acos(x) if -1.0 <= x <= 1.0 else NAN


_LOG2 = math.log(2.0)


def _asinh(v: float) -> float:  # literally log(v + sqrt(v*v+1)), as in Seamly2D
    return _log(v + _sqrt(v * v + 1))


def _acosh(v: float) -> float:
    return _log(v + _sqrt(v * v - 1))


def _atanh(v: float) -> float:
    return 0.5 * _log(c_div(1 + v, 1 - v))


def _rint(v: float) -> float:  # qFloor(v + 0.5)
    if math.isnan(v) or math.isinf(v):
        return v
    return float(math.floor(v + 0.5))


def _sign(v: float) -> float:
    return -1.0 if v < 0 else (1.0 if v > 0 else 0.0)


# qMin / qMax as Qt defines them (matters only for NaN).
def _qmin(a: float, b: float) -> float:
    return a if a < b else b


def _qmax(a: float, b: float) -> float:
    return b if a < b else a


def _sum(args: tuple[float, ...]) -> float:
    total = 0.0
    for a in args:
        total += a
    return total


def _avg(args: tuple[float, ...]) -> float:
    return _sum(args) / float(len(args))


def _min(args: tuple[float, ...]) -> float:
    res = args[0]
    for a in args:
        res = _qmin(res, a)
    return res


def _max(args: tuple[float, ...]) -> float:
    res = args[0]
    for a in args:
        res = _qmax(res, a)
    return res


@dataclass(frozen=True, slots=True)
class Function:
    name: str
    min_args: int
    max_args: int | None  # None = variable number of arguments
    fn: Callable[..., float]


def _f(name: str, n: int, fn: Callable[..., float]) -> Function:
    return Function(name, n, n, fn)


def _v(name: str, fn: Callable[[tuple[float, ...]], float]) -> Function:
    def call(*args: float) -> float:
        return fn(args)

    return Function(name, 1, None, call)


_sin = _guard(math.sin)
_cos = _guard(math.cos)
_tan = _guard(math.tan)
_cosh = _guard(math.cosh)
_tanh = _guard(math.tanh)


def _sin_d(v: float) -> float:
    return _sin(deg_to_rad(v))


def _cos_d(v: float) -> float:
    return _cos(deg_to_rad(v))


def _tan_d(v: float) -> float:
    return _tan(deg_to_rad(v))


def _asin_d(v: float) -> float:
    return rad_to_deg(_asin(v))


def _acos_d(v: float) -> float:
    return rad_to_deg(_acos(v))


def _atan_d(v: float) -> float:
    return rad_to_deg(math.atan(v))


def _log2(v: float) -> float:
    return _log(v) / _LOG2


def _abs(v: float) -> float:
    return abs(v)


_TABLE = (
    _f("degTorad", 1, deg_to_rad),
    _f("radTodeg", 1, rad_to_deg),
    _f("sin", 1, _sin),
    _f("cos", 1, _cos),
    _f("tan", 1, _tan),
    _f("sinD", 1, _sin_d),
    _f("cosD", 1, _cos_d),
    _f("tanD", 1, _tan_d),
    _f("asin", 1, _asin),
    _f("acos", 1, _acos),
    _f("atan", 1, math.atan),
    _f("atan2", 2, math.atan2),
    _f("asinD", 1, _asin_d),
    _f("acosD", 1, _acos_d),
    _f("atanD", 1, _atan_d),
    _f("sinh", 1, _sinh),
    _f("cosh", 1, _cosh),
    _f("tanh", 1, _tanh),
    _f("asinh", 1, _asinh),
    _f("acosh", 1, _acosh),
    _f("atanh", 1, _atanh),
    _f("log2", 1, _log2),
    _f("log10", 1, _log10),
    _f("log", 1, _log10),  # `log` is base 10 in Seamly2D
    _f("ln", 1, _log),
    _f("exp", 1, _exp),
    _f("sqrt", 1, _sqrt),
    _f("sign", 1, _sign),
    _f("rint", 1, _rint),  # floor(v + 0.5), not banker's rounding
    _f("abs", 1, _abs),
    _f("fmod", 2, _fmod),
    _v("sum", _sum),
    _v("avg", _avg),
    _v("min", _min),
    _v("max", _max),
)

FUNCTIONS: dict[str, Function] = {f.name: f for f in _TABLE}

CONSTANTS: dict[str, float] = {"_pi": math.pi, "_e": math.e}
