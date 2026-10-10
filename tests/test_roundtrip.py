"""Lossless Seamly2D files: read, write back, get the same bytes; and the 0.6.8 upgrade.

`fixtures/oracle/base_set.upgraded.sm2d` is the basic set as the pinned Seamly2D saves it after
opening it (made with `YOKO_ORACLE_SAVE`, see docker/oracle/). Our `upgrade_pattern` must produce
the same bytes.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from yoko_engine.formula import FormulaError
from yoko_engine.model import COMMENT, TEXT, MeasurementSet, RawNode
from yoko_io.seamly import (
    SeamlyFileError,
    read_measurements,
    read_pattern,
    upgrade_measurements,
    upgrade_pattern,
    write_measurements,
    write_pattern,
)
from yoko_io.xmlwrite import write_document

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
BASE = FIXTURES / "patterns/base/Aldrich-Womens-6th-Ed-Basic-Blocks.sm2d"
UPGRADED = FIXTURES / "oracle/base_set.upgraded.sm2d"


def test_basic_set_writes_back_byte_for_byte() -> None:
    """Including the Windows line endings the file was saved with."""
    assert write_pattern(read_pattern(BASE)) == BASE.read_bytes()


def test_upgrade_equals_what_seamly2d_saves() -> None:
    mine = write_pattern(upgrade_pattern(read_pattern(BASE)))
    assert mine.replace(b"\r\n", b"\n") == UPGRADED.read_bytes()


def test_upgraded_file_reads_and_round_trips() -> None:
    p = read_pattern(UPGRADED)
    assert p.version == "0.7.5"
    assert write_pattern(p) == UPGRADED.read_bytes()
    assert [v.name for v in p.variables] == [v.name for v in read_pattern(BASE).variables]


def test_upgrade_changes_only_version_comment_and_variable_tags() -> None:
    old = read_pattern(BASE)
    new = upgrade_pattern(old)
    assert new.blocks == old.blocks
    assert new.variables == old.variables
    assert new.version == "0.7.5" and old.version == "0.6.8"
    assert b"<increments>" in write_pattern(old)
    assert b"<variables>" in write_pattern(new) and b"<increment" not in write_pattern(new)


def test_upgrade_never_downgrades() -> None:
    new = read_pattern(UPGRADED)
    assert upgrade_pattern(new, "0.6.9") is new


def test_unknown_format_is_refused_with_a_clear_message() -> None:
    xml = BASE.read_bytes().replace(b"<version>0.6.8</version>", b"<version>0.9.0</version>")
    with pytest.raises(SeamlyFileError, match=r"0\.9\.0 is not supported"):
        read_pattern(xml)


# ---- the writer reproduces Qt's QXmlStreamWriter formatting ----


def doc(root: RawNode) -> str:
    return write_document(root).decode()


def test_attributes_are_sorted_like_seamly2d_does() -> None:
    n = RawNode("a", (("b", "1"), ("B", "2"), ("a", "3")))
    assert doc(n) == '<?xml version="1.0" encoding="UTF-8"?>\n<a B="2" a="3" b="1"/>\n'


def test_escaping() -> None:
    n = RawNode("a", (("t", 'x<y>&"z"\'\n\t'),), '1 < 2 & 3 > 2 "q"')
    assert doc(n).endswith(
        '<a t="x&lt;y&gt;&amp;&quot;z&quot;\'&#10;&#9;">1 &lt; 2 &amp; 3 &gt; 2 &quot;q&quot;</a>\n'
    )


def test_nesting_indent_comments_and_empty_elements() -> None:
    n = RawNode(
        "p",
        (),
        "",
        (
            RawNode(COMMENT, (), "hi"),
            RawNode("e"),
            RawNode("t", (), "text"),
            RawNode("g", (), "", (RawNode("h"),)),
        ),
    )
    assert doc(n) == (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<p>\n    <!--hi-->\n    <e/>\n    <t>text</t>\n    <g>\n        <h/>\n    </g>\n</p>\n"
    )


# Expected strings below are what Qt 6.4's real QXmlStreamWriter printed for the same calls
# (autoFormatting on, indent 4).
def test_mixed_content_matches_qt() -> None:
    t = lambda s: RawNode(TEXT, (), s)  # noqa: E731
    b = RawNode("b")
    k = RawNode(COMMENT, (), "k")
    decl = '<?xml version="1.0" encoding="UTF-8"?>\n'
    assert doc(RawNode("p", (), "", (t("a"), b, t("c")))) == decl + "<p>a<b/>c</p>\n"
    assert doc(RawNode("p", (), "", (t("a"), b))) == decl + "<p>a<b/>\n</p>\n"
    assert doc(RawNode("p", (), "", (b, t("c")))) == decl + "<p>\n    <b/>c</p>\n"
    assert doc(RawNode("p", (), "", (t("a"), k, b))) == decl + "<p>a<!--k-->\n    <b/>\n</p>\n"
    assert doc(RawNode("p", (), "", (b, k))) == decl + "<p>\n    <b/>\n    <!--k-->\n</p>\n"


def test_comments_and_text_survive_a_read() -> None:
    xml = (
        b'<?xml version="1.0" encoding="UTF-8"?>\n<pattern>\n    <!--c-->\n'
        b"    <version>0.7.5</version>\n"
        b"    <unit>cm</unit>\n    <notes>some\nnotes</notes>\n</pattern>\n"
    )
    assert write_pattern(read_pattern(xml)) == xml


# ---- measurement files ------------------------------------------------------------------------

SMMS = FIXTURES / "measurements/Aldrich-Womens-MultiSize-06-14.smms"
SMMS_CONVERTED = FIXTURES / "oracle/base_set.measurements.converted.smms"


def canonical_tree(n: RawNode) -> object:
    """A RawNode tree with attribute order ignored (Seamly2D's converter does not sort them)."""
    return (n.tag, sorted(n.attrs), n.text, [canonical_tree(c) for c in n.children])


def canonical_document(t: MeasurementSet) -> object:
    d = t.document
    assert d is not None
    return (d.root_tag, sorted(d.root_attrs), [canonical_tree(c) for c in d.children])


def test_multisize_table_writes_back_byte_for_byte() -> None:
    table = read_measurements(SMMS)
    assert (table.kind, table.version) == ("multisize", "0.4.4")
    assert write_measurements(table) == SMMS.read_bytes()


def test_multisize_upgrade_equals_what_seamly2d_converts() -> None:
    """`MultiSizeConverter` made 0.4.5 from our 0.4.4 file: root `vst` became `smms`."""
    mine = upgrade_measurements(read_measurements(SMMS))
    real = read_measurements(SMMS_CONVERTED)
    assert (mine.version, mine.document.root_tag) == ("0.4.5", "smms")  # type: ignore[union-attr]
    assert canonical_document(mine) == canonical_document(real)
    assert mine.values() == real.values()


def test_measurement_upgrade_is_refused_below_the_ported_steps() -> None:
    old = SMMS.read_bytes().replace(b"<version>0.4.4</version>", b"<version>0.4.2</version>")
    with pytest.raises(SeamlyFileError, match="not supported"):
        upgrade_measurements(read_measurements(old))


def test_individual_measurements_can_be_formulas() -> None:
    xml = (
        b'<?xml version="1.0" encoding="UTF-8"?>\n<smis>\n    <version>0.3.4</version>\n'
        b"    <unit>cm</unit>\n    <body-measurements>\n"
        b'        <m name="a" value="10"/>\n        <m name="b" value="(a + 5) * 2"/>\n'
        b'        <m name="c" value="b/a"/>\n    </body-measurements>\n</smis>\n'
    )
    table = read_measurements(xml)
    assert table.kind == "individual"
    assert table.values() == {"a": 10.0, "b": 30.0, "c": 3.0}
    assert write_measurements(table) == xml


def test_individual_measurement_loop_is_an_error() -> None:
    xml = (
        b"<smis><version>0.3.4</version><unit>cm</unit><body-measurements>"
        b'<m name="a" value="b"/><m name="b" value="a"/></body-measurements></smis>'
    )
    with pytest.raises(FormulaError, match="depend on"):
        read_measurements(xml).values()
