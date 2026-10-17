"""Which pieces an episode touched, so that only they are computed at `done`.

Cleaning a piece's outline is the costly part of evaluating a pattern (about 30 ms a piece), and
most plans change one or two pieces of the basic set's six. A piece is touched when it is new,
when its outline follows other objects than at the start, or when any object it follows moved.
"""

from __future__ import annotations

from yoko_engine.model import Pattern
from yoko_engine.pieces import piece_nodes
from yoko_engine.pieces_edit import pieces_of
from yoko_engine.session import PatternSession
from yoko_tools.teacher import signature


def _outlines(pattern: Pattern) -> dict[int, tuple[tuple[int, str, bool, bool], ...]]:
    """piece id -> its nodes as (the drawn object each follows, type, reverse, excluded). An object
    a union made has no drawn object: it is recorded as the negative of its node id."""
    out: dict[int, tuple[tuple[int, str, bool, bool], ...]] = {}
    for _, piece, modeling in pieces_of(pattern):
        copies = {
            m.get("id") or "": int(m.get("idObject") or 0)
            for m in modeling.children
            if (m.get("idObject") or "").isdigit()
        }
        nodes = tuple(
            (copies.get(str(n.id), -n.id), n.type, n.reverse, n.excluded)
            for n in piece_nodes(piece)
        )
        out[int(piece.get("id") or 0)] = nodes
    return out


def touched_pieces(start: PatternSession, now: PatternSession) -> list[int]:
    """The ids of the pieces of `now` that differ from the start."""
    before = _outlines(start.pattern)
    after = _outlines(now.pattern)
    ev0, ev1 = start.evaluation, now.evaluation
    touched: list[int] = []
    for pid, nodes in after.items():
        if pid not in before or before[pid] != nodes:
            touched.append(pid)
            continue
        for source, *_ in nodes:
            if source < 0:
                touched.append(pid)  # made by a union
                break
            if signature(ev0, source) != signature(ev1, source):
                touched.append(pid)
                break
    return touched
