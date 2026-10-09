"""The public `Formula` object: parse once, evaluate many times, know its dependencies."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache

from yoko_engine.formula.ast import Binary, Call, Name, Neg, Node, Num, Ternary
from yoko_engine.formula.errors import FormulaError, FormulaErrorCode
from yoko_engine.formula.evaluate import evaluate_node
from yoko_engine.formula.parser import parse_tree


def _collect_names(node: Node, out: list[Name]) -> None:
    match node:
        case Num():
            return
        case Name():
            out.append(node)
        case Neg(operand=o):
            _collect_names(o, out)
        case Binary(left=left, right=right):
            _collect_names(left, out)
            _collect_names(right, out)
        case Call(args=args):
            for a in args:
                _collect_names(a, out)
        case Ternary(cond=c, then=t, otherwise=e):
            _collect_names(c, out)
            _collect_names(t, out)
            _collect_names(e, out)


@dataclass(frozen=True, slots=True)
class Formula:
    """A parsed formula. `names` are the dependency edges: every measurement, variable and
    geometry reference it mentions, in order of first appearance."""

    text: str
    root: Node
    names: tuple[str, ...]
    _refs: tuple[Name, ...]

    def evaluate(self, values: Mapping[str, float]) -> float:
        """Evaluate against `values`.

        Like Seamly2D, every name must be defined even if it sits in a branch of `?:` that is not
        taken, so a formula's validity does not depend on its inputs.
        """
        for ref in self._refs:
            if ref.name not in values:
                raise FormulaError(
                    FormulaErrorCode.UNDEFINED_NAME,
                    f"{ref.name!r} is not a known measurement, variable or object",
                    self.text,
                    ref.pos,
                    ref.name,
                    hint="check the spelling; variables start with '#'",
                )
        return evaluate_node(self.root, values)


@lru_cache(maxsize=8192)
def parse(text: str) -> Formula:
    """Parse `text` (cached). Raises `FormulaError`; never returns a partial result."""
    root = parse_tree(text)
    refs: list[Name] = []
    _collect_names(root, refs)
    seen: dict[str, None] = {}
    for r in refs:
        seen.setdefault(r.name)
    return Formula(text, root, tuple(seen), tuple(refs))
