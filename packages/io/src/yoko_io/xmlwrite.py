"""Write XML the way Seamly2D does.

Seamly2D saves with `QXmlStreamWriter` (auto-formatting, 4-space indent), writing each element's
attributes sorted by name (`VDomDocument::SaveCanonicalXML`, `src/libs/ifc/xml/vdomdocument.cpp`).
This module reproduces that output byte for byte, so a file Seamly2D saved is written back unchanged
and a file we change differs from Seamly2D's own save only where our change is.

The formatting rules are those of Qt's writer: an element with no content is `<a/>`; an element that
holds text keeps it inline (`<a>text</a>`); otherwise each child starts on its own line, indented,
and the closing tag follows on its own line. Text and attribute values both escape `& < > "`;
attribute values also escape tab, newline and carriage return.
"""

from __future__ import annotations

from collections.abc import Iterable

from yoko_engine.model import COMMENT, TEXT, RawNode

INDENT = "    "


def _escape_text(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _escape_attr(s: str) -> str:
    return _escape_text(s).replace("\n", "&#10;").replace("\r", "&#13;").replace("\t", "&#9;")


def sorted_attrs(attrs: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    """Seamly2D keeps attributes in a `QMap`, so they come out sorted by UTF-16 code units.
    A repeated name keeps its last value, as the map does."""
    unique = dict(attrs)
    return sorted(unique.items(), key=lambda kv: kv[0].encode("utf-16-be"))


class _Writer:
    """The subset of `QXmlStreamWriter` (auto-formatting on) that Seamly2D files use."""

    def __init__(self, newline: str, canonical: bool = True) -> None:
        self.out: list[str] = []
        self.newline = newline
        self.canonical = canonical
        self.depth = 0
        self.in_start = False  # a start tag is written but not yet closed with ">"
        self.wrote_text = False  # text was written since the last tag (Qt: wroteSomething)
        self.last_was_start = False

    def _indent(self, level: int) -> None:
        self.out.append(self.newline + INDENT * level)

    def _finish_start(self, contents: bool) -> bool:
        had = self.wrote_text
        self.wrote_text = contents
        if self.in_start:
            self.out.append(">")
            self.in_start = False
        return had

    def start(self, tag: str, attrs: Iterable[tuple[str, str]]) -> None:
        if not self._finish_start(False):
            self._indent(self.depth)
        self.out.append("<" + tag)
        for k, v in sorted_attrs(attrs) if self.canonical else dict(attrs).items():
            self.out.append(f' {k}="{_escape_attr(v)}"')
        self.depth += 1
        self.in_start = self.last_was_start = True

    def end(self, tag: str) -> None:
        self.depth -= 1
        if self.in_start:
            self.out.append("/>")
            self.in_start = self.last_was_start = False
            return
        if not self._finish_start(False) and not self.last_was_start:
            self._indent(self.depth)
        self.out.append(f"</{tag}>")
        self.last_was_start = False

    def text(self, s: str) -> None:
        self._finish_start(True)
        self.out.append(_escape_text(s))
        self.last_was_start = False

    def comment(self, s: str) -> None:
        if not self._finish_start(False):
            self._indent(self.depth)
        self.out.append(f"<!--{s}-->")
        self.in_start = self.last_was_start = False


def write_node(w: _Writer, n: RawNode) -> None:
    if n.tag == COMMENT:
        w.comment(n.text)
    elif n.tag == TEXT:
        w.text(n.text)
    else:
        w.start(n.tag, n.attrs)
        if n.text:
            w.text(n.text)
        for c in n.children:
            write_node(w, c)
        w.end(n.tag)


DECLARATION = '<?xml version="1.0" encoding="UTF-8"?>'


def write_document(
    root: RawNode,
    newline: str = "\n",
    declaration: str = DECLARATION,
    *,
    canonical: bool = True,
) -> bytes:
    """Serialise one element tree as a Seamly2D file (UTF-8, XML declaration, final newline).

    `canonical=False` keeps each element's attributes in the order given instead of sorting them.
    """
    w = _Writer(newline, canonical)
    w.out.append(declaration)
    write_node(w, root)
    w.out.append(newline)
    return "".join(w.out).encode("utf-8")
