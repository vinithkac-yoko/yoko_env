"""Read Seamly2D files into the engine's model.

Phase 1 reads pattern format 0.6.8 (`.sm2d` with `<increments>`) and multisize measurement files
(`.smms`/`.vst`). Later formats (0.6.9 to 0.7.5) and lossless writing come in Phase 2; nothing the
reader does not interpret is dropped, it is carried in `RawNode`s and `Obj.attrs`.

XML is parsed with defusedxml: files can come from outside (studio imports).
"""

from __future__ import annotations

from pathlib import Path
from typing import Final
from xml.etree.ElementTree import Element

from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException
from yoko_engine.model import (
    DraftBlock,
    Measurement,
    MeasurementSet,
    Obj,
    Pattern,
    RawNode,
    Variable,
)

SUPPORTED_PATTERN_VERSIONS: Final = ("0.6.8",)


class SeamlyFileError(Exception):
    """A file could not be read. The message says what is wrong and where."""


def _attrs(el: Element) -> tuple[tuple[str, str], ...]:
    return tuple(el.attrib.items())


def raw_node(el: Element) -> RawNode:
    text = (el.text or "").strip()
    return RawNode(el.tag, _attrs(el), text, tuple(raw_node(c) for c in el))


def _text(root: Element, tag: str) -> str:
    el = root.find(tag)
    return (el.text or "").strip() if el is not None else ""


def _parse(source: str | bytes | Path) -> Element:
    try:
        root = (
            SafeET.parse(source).getroot()
            if isinstance(source, Path)
            else SafeET.fromstring(source)
        )
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


def read_pattern(source: str | bytes | Path) -> Pattern:
    """Read a pattern (`.sm2d`) of format 0.6.8."""
    root = _parse(source)
    if root.tag != "pattern":
        raise SeamlyFileError(f"expected a <pattern> file, found <{root.tag}>")
    version = _text(root, "version")
    if version not in SUPPORTED_PATTERN_VERSIONS:
        raise SeamlyFileError(
            f"pattern format {version or '(none)'} is not supported yet "
            f"(this build reads {', '.join(SUPPORTED_PATTERN_VERSIONS)})"
        )
    unit = _text(root, "unit")
    if unit not in ("cm", "mm", "inch"):
        raise SeamlyFileError(f"unknown pattern unit {unit!r}")

    variables: list[Variable] = []
    blocks: list[DraftBlock] = []
    header: list[RawNode] = []
    for el in root:
        if el.tag in ("increments", "variables"):
            for inc in el:
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
            calc = el.find("calculation")
            objects = tuple(_object(c) for c in calc) if calc is not None else ()
            sections = tuple(raw_node(c) for c in el if c.tag != "calculation")
            blocks.append(DraftBlock(el.get("name", ""), objects, sections))
        else:
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
    )


def read_measurements(source: str | bytes | Path) -> MeasurementSet:
    """Read a multisize measurement table (`.smms`, root `<vst>`)."""
    root = _parse(source)
    if root.tag != "vst":
        raise SeamlyFileError(
            f"expected a multisize table (<vst>), found <{root.tag}>; "
            "individual measurement files are not supported yet"
        )
    size = root.find("size")
    height = root.find("height")
    body = root.find("body-measurements")
    if size is None or height is None or body is None:
        raise SeamlyFileError("measurement table needs <size>, <height> and <body-measurements>")
    try:
        rows = tuple(
            Measurement(
                m.attrib["name"],
                float(m.attrib["base"]),
                float(m.get("size_increase", "0")),
                float(m.get("height_increase", "0")),
            )
            for m in body
        )
        return MeasurementSet(
            unit=_text(root, "unit"),
            base_size=float(size.attrib["base"]),
            base_height=float(height.attrib["base"]),
            measurements=rows,
        )
    except (KeyError, ValueError) as err:
        raise SeamlyFileError(f"bad measurement row: {err}") from err
