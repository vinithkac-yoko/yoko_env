"""Evaluation of a parsed formula.

Semantics ported from Seamly2D's bytecode interpreter (qmuparserbase.cpp `ParseCmdCodeBulk`):
- comparisons yield 1.0 or 0.0; `==` and `!=` are fuzzy (Qt qFuzzyCompare, zero handled apart)
- `&&` and `||` treat any non-zero double as true (NaN counts as true, like a C++ bool cast)
- `cond ? a : b` takes `b` when `cond` is fuzzily zero (|cond| <= 1e-12); one branch is evaluated
- division by zero is IEEE (inf or nan), never an error
"""

from __future__ import annotations

from collections.abc import Mapping

from yoko_engine.formula.ast import Binary, Call, Name, Neg, Node, Num, Ternary
from yoko_engine.formula.functions import (
    FUNCTIONS,
    c_div,
    c_pow,
    fuzzy_compare_possible_nulls,
    fuzzy_is_null,
)


def _as_bool(x: float) -> bool:
    return x != 0.0 or x != x  # NaN converts to true, as static_cast<bool>(nan) does


def evaluate_node(node: Node, values: Mapping[str, float]) -> float:
    match node:
        case Num(value=v):
            return v
        case Name(name=n):
            return values[n]
        case Neg(operand=o):
            return -evaluate_node(o, values)
        case Ternary(cond=c, then=t, otherwise=e):
            if fuzzy_is_null(evaluate_node(c, values)):
                return evaluate_node(e, values)
            return evaluate_node(t, values)
        case Call(func=f, args=args):
            return FUNCTIONS[f].fn(*[evaluate_node(a, values) for a in args])
        case Binary(op=op, left=l_, right=r_):
            a = evaluate_node(l_, values)
            b = evaluate_node(r_, values)
            return _binary(op, a, b)
    raise AssertionError(f"unreachable: {node!r}")  # pragma: no cover


def _binary(op: str, a: float, b: float) -> float:
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if op == "/":
        return c_div(a, b)
    if op == "^":
        return c_pow(a, b)
    if op == "<":
        return float(a < b)
    if op == ">":
        return float(a > b)
    if op == "<=":
        return float(a <= b)
    if op == ">=":
        return float(a >= b)
    if op == "==":
        return float(fuzzy_compare_possible_nulls(a, b))
    if op == "!=":
        return float(not fuzzy_compare_possible_nulls(a, b))
    if op == "&&":
        return float(_as_bool(a) and _as_bool(b))
    if op == "||":
        return float(_as_bool(a) or _as_bool(b))
    raise AssertionError(f"unknown operator {op!r}")  # pragma: no cover
