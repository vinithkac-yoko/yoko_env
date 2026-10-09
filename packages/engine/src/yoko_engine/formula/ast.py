"""Formula syntax tree. Immutable, so a parsed formula can be shared and cached."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Num:
    value: float
    pos: int


@dataclass(frozen=True, slots=True)
class Name:
    """A measurement, variable or geometry reference (`Line_A_B`, `#CM`, `bust_circ`)."""

    name: str
    pos: int


@dataclass(frozen=True, slots=True)
class Neg:
    """Seamly2D's only infix operator: unary minus."""

    operand: Node
    pos: int


@dataclass(frozen=True, slots=True)
class Binary:
    op: str  # one of: + - * / ^ < > <= >= == != && ||
    left: Node
    right: Node
    pos: int


@dataclass(frozen=True, slots=True)
class Call:
    func: str
    args: tuple[Node, ...]
    pos: int


@dataclass(frozen=True, slots=True)
class Ternary:
    cond: Node
    then: Node
    otherwise: Node
    pos: int


Node = Num | Name | Neg | Binary | Call | Ternary
