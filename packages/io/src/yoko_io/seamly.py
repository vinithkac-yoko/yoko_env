"""Read Seamly2D files into the engine's model.

Patterns (`.sm2d`) of formats 0.6.8 to 0.7.5 and multisize measurement files (`.smms`/`.vst`).
Nothing the reader does not interpret is dropped, it is carried in `RawNode`s and `Obj.attrs`, and
`write_pattern` writes it back the way Seamly2D saves it (see `yoko_io.xmlwrite`).

XML is parsed with defusedxml: files can come from outside (studio imports).
"""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path
from typing import Final
from xml.etree.ElementTree import Comment, Element, TreeBuilder

from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException
from yoko_engine.formula import is_valid_name
from yoko_engine.model import (
    COMMENT,
    TEXT,
    DraftBlock,
    Measurement,
    MeasurementSet,
    Obj,
    Pattern,
    RawDocument,
    RawNode,
    Variable,
)

from yoko_io.xmlwrite import write_document

SUPPORTED_PATTERN_VERSIONS: Final = (
    "0.6.8",
    "0.6.9",
    "0.7.0",
    "0.7.1",
    "0.7.2",
    "0.7.3",
    "0.7.4",
    "0.7.5",
)


class SeamlyFileError(Exception):
    """A file could not be read. The message says what is wrong and where."""


def _attrs(el: Element) -> tuple[tuple[str, str], ...]:
    return tuple(el.attrib.items())


def _blank(s: str | None) -> bool:
    return s is None or not s.strip()


def raw_node(el: Element) -> RawNode:
    """An element as a `RawNode`, comments and text included.

    Seamly2D's XML reader (QDom) drops text that is only whitespace, so does this.
    """
    if el.tag is Comment:
        return RawNode(COMMENT, (), el.text or "")
    kids: list[RawNode] = []
    if len(el) == 0:
        return RawNode(el.tag, _attrs(el), "" if _blank(el.text) else el.text or "")
    if not _blank(el.text):
        kids.append(RawNode(TEXT, (), el.text or ""))
    for c in el:
        kids.append(raw_node(c))
        if not _blank(c.tail):
            kids.append(RawNode(TEXT, (), c.tail or ""))
    return RawNode(el.tag, _attrs(el), "", tuple(kids))


def _text(root: Element, tag: str) -> str:
    el = root.find(tag)
    return (el.text or "").strip() if el is not None else ""


def _to_bytes(source: str | bytes | Path) -> bytes:
    if isinstance(source, Path):
        return source.read_bytes()
    return source.encode("utf-8") if isinstance(source, str) else source


def _parse(data: bytes) -> Element:
    try:
        parser = SafeET.DefusedXMLParser(target=TreeBuilder(insert_comments=True))
        parser.feed(data)
        root = parser.close()
    except SafeET.ParseError as err:
        raise SeamlyFileError(f"not valid XML: {err}") from err
    except DefusedXmlException as err:
        raise SeamlyFileError(
            f"the file uses XML features that are not allowed (entities or DTDs): {err}"
        ) from err
    if root is None:
        raise SeamlyFileError("the file is empty")
    return root


def _object(el: Element) -> Obj:
    raw_id = el.get("id")
    if raw_id is None or not raw_id.isdigit():
        raise SeamlyFileError(f"<{el.tag}> without a numeric id: {dict(el.attrib)}")
    kind = el.get("type") or el.tag
    return Obj(int(raw_id), el.tag, kind, _attrs(el), tuple(raw_node(c) for c in el))


def _block(el: Element) -> DraftBlock:
    objects: tuple[Obj, ...] = ()
    sections: list[RawNode] = []
    calc_index = -1
    for i, c in enumerate(el):
        if c.tag == "calculation":
            if c.attrib or any(k.tag is Comment or not _blank(k.tail) for k in c):
                raise SeamlyFileError(
                    "attributes or comments inside <calculation> are not supported yet"
                )
            calc_index = i
            objects = tuple(_object(k) for k in c)
        else:
            sections.append(raw_node(c))
            if not _blank(c.tail):
                sections.append(RawNode(TEXT, (), c.tail or ""))
    extra = tuple((k, v) for k, v in el.attrib.items() if k != "name")
    return DraftBlock(el.get("name", ""), objects, tuple(sections), extra, calc_index)


def read_pattern(source: str | bytes | Path) -> Pattern:
    """Read a pattern (`.sm2d`) of format 0.6.8 to 0.7.5."""
    data = _to_bytes(source)
    root = _parse(data)
    if root.tag != "pattern":
        raise SeamlyFileError(f"expected a <pattern> file, found <{root.tag}>")
    version = _text(root, "version")
    if version not in SUPPORTED_PATTERN_VERSIONS:
        raise SeamlyFileError(
            f"pattern format {version or '(none)'} is not supported "
            f"(this build reads {SUPPORTED_PATTERN_VERSIONS[0]} "
            f"to {SUPPORTED_PATTERN_VERSIONS[-1]})"
        )
    unit = _text(root, "unit")
    if unit not in ("cm", "mm", "inch"):
        raise SeamlyFileError(f"unknown pattern unit {unit!r}")

    variables: list[Variable] = []
    blocks: list[DraftBlock] = []
    header: list[RawNode] = []
    layout: list[tuple[str, int]] = []
    for el in root:
        if el.tag in ("increments", "variables"):
            if any(k == "variables" for k, _ in layout):
                raise SeamlyFileError("more than one variables section")
            layout.append(("variables", 0))
            for inc in el:
                if inc.tag is Comment:
                    raise SeamlyFileError("comments inside <variables> are not supported yet")
                known = {"name", "formula", "description"}
                variables.append(
                    Variable(
                        inc.get("name", ""),
                        inc.get("formula", "0"),
                        inc.get("description", ""),
                        tuple((k, v) for k, v in inc.attrib.items() if k not in known),
                    )
                )
        elif el.tag == "draftBlock":
            layout.append(("block", len(blocks)))
            blocks.append(_block(el))
        else:
            layout.append(("raw", len(header)))
            header.append(raw_node(el))

    ids = [o.id for b in blocks for o in b.objects]
    if len(ids) != len(set(ids)):
        raise SeamlyFileError("duplicate object ids in the pattern")
    return Pattern(
        unit=unit,
        version=version,
        measurements_file=_text(root, "measurements"),
        variables=tuple(variables),
        blocks=tuple(blocks),
        header=tuple(header),
        layout=tuple(layout),
        line_ending="\r\n" if b"\r\n" in data else "\n",
        root_attrs=_attrs(root),
    )


def _obj_node(o: Obj) -> RawNode:
    return RawNode(o.tag, o.attrs, "", o.children)


def _block_node(b: DraftBlock) -> RawNode:
    calc = RawNode("calculation", (), "", tuple(_obj_node(o) for o in b.objects))
    kids = list(b.sections)
    if b.calculation_index >= 0:
        kids.insert(min(b.calculation_index, len(kids)), calc)
    return RawNode("draftBlock", (("name", b.name), *b.extra_attrs), "", tuple(kids))


def _variables_node(pattern: Pattern) -> RawNode:
    old = _version_key(pattern.version) < _version_key("0.6.9")
    tag, child = ("increments", "increment") if old else ("variables", "variable")
    rows = tuple(
        RawNode(
            child,
            (("name", v.name), ("formula", v.formula), ("description", v.description), *v.extra),
        )
        for v in pattern.variables
    )
    return RawNode(tag, (), "", rows)


def _version_key(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))


def pattern_node(pattern: Pattern) -> RawNode:
    """The whole pattern as an element tree, in the order the file had."""
    order = list(pattern.layout)
    seen_blocks = {i for kind, i in order if kind == "block"}
    order += [("block", i) for i in range(len(pattern.blocks)) if i not in seen_blocks]
    if pattern.variables and not any(kind == "variables" for kind, _ in order):
        order.insert(len(pattern.header), ("variables", 0))
    overrides = {
        "version": pattern.version,
        "unit": pattern.unit,
        "measurements": pattern.measurements_file,
    }
    kids: list[RawNode] = []
    for kind, i in order:
        if kind == "raw" and i < len(pattern.header):
            n = pattern.header[i]
            if n.tag in overrides and not n.children:
                n = RawNode(n.tag, n.attrs, overrides[n.tag])
            kids.append(n)
        elif kind == "variables":
            kids.append(_variables_node(pattern))
        elif kind == "block" and i < len(pattern.blocks):
            kids.append(_block_node(pattern.blocks[i]))
    return RawNode("pattern", pattern.root_attrs, "", tuple(kids))


PINNED_FORMAT: Final = SUPPORTED_PATTERN_VERSIONS[-1]
PINNED_SEAMLY2D: Final = "2026.10.5.154"  # the Seamly2D release the oracle is pinned to (ADR 0002)


def upgrade_pattern(
    pattern: Pattern, target: str = PINNED_FORMAT, app_version: str = PINNED_SEAMLY2D
) -> Pattern:
    """What Seamly2D does when it opens an older pattern and saves it again.

    Source: `VPatternConverter` (`src/libs/ifc/xml/vpatternconverter.cpp`). From 0.6.8 to 0.7.5 the
    only change to the content is 0.6.9 renaming `<increments>` to `<variables>`: the other steps
    only raise the version. On save, Seamly2D also rewrites the leading comment with its own version
    (`VPattern::SaveDocument`). Never downgrades.
    """
    if target not in SUPPORTED_PATTERN_VERSIONS:
        raise SeamlyFileError(f"cannot upgrade to unknown format {target}")
    if _version_key(pattern.version) >= _version_key(target):
        return pattern
    header = list(pattern.header)
    # the leading comment is the first child of <pattern>, when there is one
    first = pattern.layout[0] if pattern.layout else None
    if first is not None and first[0] == "raw" and header[first[1]].tag == COMMENT:
        header[first[1]] = RawNode(
            COMMENT, (), f"Pattern created with Seamly2D v{app_version} (https://seamly.io)."
        )
    return replace(pattern, version=target, header=tuple(header))


def write_pattern(pattern: Pattern, *, canonical: bool = True) -> bytes:
    """Write a pattern the way Seamly2D saves it, in the format version the pattern has.

    `canonical` sorts attributes by name, as Seamly2D does. Pass False to keep the attribute order
    the file had (files from before that rule, or from other tools).
    """
    return write_document(pattern_node(pattern), pattern.line_ending, canonical=canonical)


MULTISIZE_VERSIONS: Final = ("0.4.0", "0.4.1", "0.4.2", "0.4.3", "0.4.4", "0.4.5")
INDIVIDUAL_VERSIONS: Final = ("0.3.0", "0.3.1", "0.3.2", "0.3.3", "0.3.4")
PINNED_MULTISIZE: Final = MULTISIZE_VERSIONS[-1]
PINNED_INDIVIDUAL: Final = INDIVIDUAL_VERSIONS[-1]
_DECLARATION = re.compile(rb"^\s*(<\?xml[^>]*\?>)")


def _measurement_document(root: Element, data: bytes) -> RawDocument:
    decl = _DECLARATION.match(data)
    return RawDocument(
        root.tag,
        _attrs(root),
        tuple(raw_node(c) for c in root),
        "\r\n" if b"\r\n" in data else "\n",
        decl.group(1).decode("utf-8") if decl else '<?xml version="1.0" encoding="UTF-8"?>',
    )


def _check_name(name: str | None) -> str:
    if not name:
        raise SeamlyFileError("a measurement without a name")
    if not is_valid_name(name):
        raise SeamlyFileError(
            f"{name!r} is not a valid measurement name (no blanks or operators, "
            "and it cannot start with a digit)"
        )
    return name


def _individual_row(m: Element) -> Measurement:
    name = _check_name(m.attrib.get("name"))
    value = m.attrib.get("value", "").strip()
    if not value:
        raise SeamlyFileError(f"measurement {name!r} has no value")
    try:
        return Measurement(name, float(value))
    except ValueError:
        return Measurement(name, 0.0, formula=value)  # e.g. "(height_neck_back - height_knee)"


def read_measurements(source: str | bytes | Path) -> MeasurementSet:
    """Read a measurement file.

    Multisize (`.smms`, root `<smms>` or `<vst>`, formats 0.4.0 to 0.4.5)
    or individual (`.smis`, root `<smis>` or `<vit>`, formats 0.3.0 to 0.3.4)."""
    data = _to_bytes(source)
    root = _parse(data)
    if root.tag in ("vst", "smms"):
        kind, allowed = "multisize", MULTISIZE_VERSIONS
    elif root.tag in ("vit", "smis"):
        kind, allowed = "individual", INDIVIDUAL_VERSIONS
    else:
        raise SeamlyFileError(f"expected a measurement file (<smms> or <smis>), found <{root.tag}>")
    version = _text(root, "version")
    if version not in allowed:
        raise SeamlyFileError(
            f"{kind} measurement format {version or '(none)'} is not supported "
            f"(this build reads {allowed[0]} to {allowed[-1]})"
        )
    body = root.find("body-measurements")
    if body is None:
        raise SeamlyFileError("measurement file needs <body-measurements>")
    document = _measurement_document(root, data)
    names = [m.attrib.get("name") for m in body if m.tag is not Comment]
    dupes = sorted({n for n in names if n and names.count(n) > 1})
    if dupes:
        raise SeamlyFileError(f"measurement names used more than once: {', '.join(dupes)}")
    try:
        if kind == "individual":
            rows = tuple(_individual_row(m) for m in body if m.tag is not Comment)
            return MeasurementSet(
                unit=_text(root, "unit"),
                base_size=0.0,
                base_height=0.0,
                measurements=rows,
                kind=kind,
                version=version,
                document=document,
            )
        size, height = root.find("size"), root.find("height")
        if size is None or height is None:
            raise SeamlyFileError(
                "measurement table needs <size>, <height> and <body-measurements>"
            )
        rows = tuple(
            Measurement(
                _check_name(m.attrib.get("name")),
                float(m.attrib["base"]),
                float(m.get("size_increase", "0")),
                float(m.get("height_increase", "0")),
            )
            for m in body
            if m.tag is not Comment
        )
        return MeasurementSet(
            unit=_text(root, "unit"),
            base_size=float(size.attrib["base"]),
            base_height=float(height.attrib["base"]),
            measurements=rows,
            kind=kind,
            version=version,
            document=document,
        )
    except (KeyError, ValueError) as err:
        raise SeamlyFileError(f"bad measurement row ({err!r})") from err


def upgrade_measurements(table: MeasurementSet) -> MeasurementSet:
    """Bring a measurement file to the format the pinned Seamly2D writes.

    Source: `MultiSizeConverter::convertToVer0_4_5` and `IndividualSizeConverter::convertToVer0_3_4`
    (`src/libs/ifc/xml/`): the root element is renamed (`vst` to `smms`, `vit` to `smis`) and the
    version raised. Older steps change content and are not ported: files older than 0.4.4
    (multisize) or 0.3.3 (individual) are refused here (open them in Seamly2D once to upgrade them).
    """
    if table.document is None:
        raise SeamlyFileError("this measurement table was not read from a file")
    pinned, oldest, new_root = (
        (PINNED_MULTISIZE, "0.4.4", "smms")
        if table.kind == "multisize"
        else (PINNED_INDIVIDUAL, "0.3.3", "smis")
    )
    if _version_key(table.version) >= _version_key(pinned):
        return table
    if _version_key(table.version) < _version_key(oldest):
        raise SeamlyFileError(
            f"upgrading {table.kind} measurements from {table.version} is not supported "
            f"(from {oldest} it is)"
        )
    kids = tuple(
        RawNode(n.tag, n.attrs, pinned, n.children) if n.tag == "version" else n
        for n in table.document.children
    )
    doc = replace(table.document, root_tag=new_root, children=kids)
    return replace(table, version=pinned, document=doc)


def write_measurements(table: MeasurementSet, *, canonical: bool = True) -> bytes:
    """Write a measurement file read with `read_measurements`, the way Seamly2D saves it."""
    d = table.document
    if d is None:
        raise SeamlyFileError("this measurement table was not read from a file")
    return write_document(
        RawNode(d.root_tag, d.root_attrs, "", d.children),
        d.line_ending,
        d.declaration,
        canonical=canonical,
    )
