"""Seamly2D's own test patterns (fixtures/external/seamly2d, see its README).

- the copies are the ones Seamly2D ships (hash manifest);
- every pattern the pinned Seamly2D saved reads and writes back byte for byte;
- the format-0.7.4 originals upgrade to exactly what Seamly2D saves;
- files we cannot or must not read fail with a clear error, never a crash;
- the engine never gets a point wrong, and reproduces at least as many as the ratchet says
  (`scripts/external_report.py --write` raises the ratchet).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from yoko_engine.evaluator import evaluate
from yoko_engine.model import MeasurementSet, RawNode
from yoko_io.seamly import (
    SeamlyFileError,
    read_measurements,
    read_pattern,
    upgrade_measurements,
    upgrade_pattern,
    write_measurements,
    write_pattern,
)

EXT = Path(__file__).resolve().parents[1] / "fixtures/external/seamly2d"
UPGRADED = sorted((EXT / "upgraded").rglob("*.sm2d"))
ORIGINAL_PATTERNS = sorted((EXT / "original").rglob("*.sm2d"))
MEASUREMENTS = sorted([*(EXT / "original").rglob("*.smis"), *(EXT / "original").rglob("*.smms")])
RATCHET: dict[str, int] = json.loads((Path(__file__).parent / "external_ratchet.json").read_text())


def rel(p: Path, base: str) -> str:
    return p.relative_to(EXT / base).as_posix()


def test_originals_are_what_seamly2d_ships() -> None:
    lines = (EXT / "MANIFEST.sha256").read_text().splitlines()
    assert len(lines) > 60
    for line in lines:
        digest, _, name = line.partition("  ")
        assert hashlib.sha256((EXT / name).read_bytes()).hexdigest() == digest, name


def test_there_are_23_upgraded_patterns() -> None:
    assert len(UPGRADED) == 23


@pytest.mark.parametrize("path", UPGRADED, ids=lambda p: rel(p, "upgraded"))
def test_seamly2d_saved_pattern_writes_back_byte_for_byte(path: Path) -> None:
    pattern = read_pattern(path)
    assert pattern.version == "0.7.5"
    assert write_pattern(pattern) == path.read_bytes()


@pytest.mark.parametrize(
    "name", ["all_tools_pattern/alltools_pattern.sm2d"], ids=lambda n: n.split("/")[0]
)
def test_format_0_7_4_originals_upgrade_to_what_seamly2d_saves(name: str) -> None:
    original = EXT / "original" / name
    pattern = read_pattern(original)
    assert pattern.version == "0.7.4"
    assert write_pattern(pattern) == original.read_bytes()  # lossless as read
    saved = (EXT / "upgraded" / name).read_bytes()
    assert write_pattern(upgrade_pattern(pattern)) == saved


@pytest.mark.parametrize("path", ORIGINAL_PATTERNS, ids=lambda p: rel(p, "original"))
def test_every_original_reads_or_fails_with_a_clear_message(path: Path) -> None:
    try:
        pattern = read_pattern(path)
    except SeamlyFileError as err:
        assert str(err)
    else:
        assert pattern.blocks or pattern.header


@pytest.mark.parametrize("path", MEASUREMENTS, ids=lambda p: rel(p, "original"))
def test_every_measurement_file_reads_losslessly_or_fails_clearly(path: Path) -> None:
    try:
        table = read_measurements(path)
    except SeamlyFileError as err:
        assert str(err)
        return
    # older files were not written by Qt, so keep their attribute order; the text must survive
    out = write_measurements(table, canonical=False)
    again = read_measurements(out)
    assert again.measurements == table.measurements
    assert again.document == table.document


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("broken1.smis", "more than once"),
        ("broken2.smis", "without a name"),
        ("broken3.smis", "has no value"),
        ("broken4.smis", "not a valid measurement name"),
    ],
)
def test_broken_measurement_files_fail_clearly(name: str, message: str) -> None:
    with pytest.raises(SeamlyFileError, match=message):
        read_measurements(EXT / "original/broken" / name)


def test_empty_files_fail_clearly() -> None:
    for p in (EXT / "original/text").iterdir():
        with pytest.raises(SeamlyFileError, match="not valid XML"):
            if p.suffix == ".sm2d":
                read_pattern(p)
            else:
                read_measurements(p)


@pytest.mark.parametrize("path", UPGRADED, ids=lambda p: rel(p, "upgraded"))
def test_engine_matches_seamly2d_on_every_point_it_computes(path: Path) -> None:
    name = rel(path, "upgraded")
    pattern = read_pattern(path)
    values: dict[str, float] = {}
    if pattern.measurements_file:
        m = EXT / "original" / Path(name).parent / pattern.measurements_file
        if m.is_file():
            values = read_measurements(m).values()
    ev = evaluate(pattern, values)
    oracle = json.loads((EXT / "oracle" / f"{name}.seamly2d.json").read_text())
    exact = 0
    for o in oracle["points"]:
        mine = ev.points.get(o["id"])
        if mine is None:
            continue
        assert (mine.p.x, mine.p.y) == (o["x_px"], o["y_px"]), (name, o["id"], o["name"])
        exact += 1
    assert exact >= RATCHET[name], f"{name}: {exact} points, the ratchet says {RATCHET[name]}"


CONVERTED = sorted((EXT / "converted").rglob("*.sm[ci]s")) + sorted(
    (EXT / "converted").rglob("*.smms")
)


@pytest.mark.parametrize("path", CONVERTED, ids=lambda p: rel(p, "converted"))
def test_measurement_upgrade_equals_what_seamly2d_converts(path: Path) -> None:
    """Seamly2D's converter kept a copy of every measurement file it upgraded on the way."""
    name = rel(path, "converted")
    original = read_measurements(EXT / "original" / name)
    real = read_measurements(path)
    if original.version in ("0.4.0", "0.4.1", "0.4.2", "0.4.3", "0.3.0", "0.3.1", "0.3.2"):
        with pytest.raises(SeamlyFileError, match="not supported"):
            upgrade_measurements(original)
        return
    mine = upgrade_measurements(original)
    assert mine.version == real.version
    assert mine.document is not None and real.document is not None
    assert mine.document.root_tag == real.document.root_tag
    assert canonical_children(mine) == canonical_children(real)
    assert mine.values() == real.values()


def canonical_children(t: MeasurementSet) -> object:
    assert t.document is not None

    def canon(n: RawNode) -> object:
        return (n.tag, sorted(n.attrs), n.text, [canon(c) for c in n.children])

    return [canon(c) for c in t.document.children]
