"""A pattern evaluated against a person's own measurement file instead of the multisize table, and
the sizes a plan is checked at."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
from yoko_engine.binding import (
    MeasurementError,
    check_measurements,
    gradation,
    individual_table,
    missing_measurements,
    size_grid,
)
from yoko_engine.evaluator import evaluate
from yoko_io.seamly import (
    individual_measurements_file,
    read_measurements,
    read_pattern,
    rebind_measurements,
    write_pattern,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
BASE = read_pattern(FIXTURES / "patterns/base/Aldrich-Womens-6th-Ed-Basic-Blocks.sm2d")
MULTI = read_measurements(FIXTURES / "measurements/Aldrich-Womens-MultiSize-06-14.smms")
SEAMLY2D = Path("/home/user/seamly2d-build/src/app/seamly2d/bin/seamly2d")


def test_a_persons_file_gives_the_same_pattern_as_the_table_row_with_the_same_numbers() -> None:
    values = MULTI.values(38, 164)
    person = read_measurements_from_bytes(individual_measurements_file(values))
    assert person.kind == "individual"
    a = evaluate(BASE, values)
    b = evaluate(BASE, check_measurements(BASE, person))
    assert not b.issues
    assert {i: (p.p.x, p.p.y) for i, p in a.points.items()} == {
        i: (p.p.x, p.p.y) for i, p in b.points.items()
    }


def read_measurements_from_bytes(data: bytes):  # type: ignore[no-untyped-def]
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "person.smis"
        path.write_bytes(data)
        return read_measurements(path)


def test_a_file_that_lacks_measurements_says_which() -> None:
    values = dict(MULTI.values())
    for gone in ("hip_circ", "waist_circ"):
        del values[gone]
    person = individual_table(values)
    assert missing_measurements(BASE, person.values()) == ["hip_circ", "waist_circ"]
    with pytest.raises(MeasurementError) as err:
        check_measurements(BASE, person)
    assert err.value.missing == ("hip_circ", "waist_circ")
    assert "hip_circ" in str(err.value)


def test_the_sizes_to_check_are_the_tables_and_a_person_has_three() -> None:
    grid = size_grid(BASE, MULTI)
    assert [p.size for p in grid[::3]] == [34, 36, 38, 40, 42]  # three heights each
    assert {p.height for p in grid} == {158.0, 164.0, 170.0}
    assert size_grid(BASE, MULTI, sizes=[34], heights=[164])[0].label == "size 34, height 164"
    person = individual_table(MULTI.values())
    points = size_grid(BASE, person)
    assert [p.label for p in points] == [
        "your measurements",
        "your measurements, nudged up",
        "your measurements, nudged down",
    ]
    own, up, down = (p.values for p in points)
    assert up["bust_circ"] == pytest.approx(own["bust_circ"] + 2)
    assert down["hip_circ"] == pytest.approx(own["hip_circ"] - 2)
    assert up["height"] == pytest.approx(own["height"] + 3)
    assert up["neck_circ"] == own["neck_circ"]  # only the nudged measurements move
    sizes, heights = gradation(BASE)
    assert 36 in sizes and 164 in heights


def test_nudged_copies_follow_the_files_unit_and_formulas() -> None:
    from yoko_engine.binding import MeasurementError, nudged_tables
    from yoko_engine.model import Measurement, MeasurementSet

    person = MeasurementSet(
        "mm",
        0.0,
        0.0,
        (
            Measurement("bust_circ", 900.0),
            Measurement("height", 1640.0),
            Measurement("half_bust", 0.0, formula="bust_circ/2"),
        ),
        kind="individual",
    )
    up, down = nudged_tables(person)
    assert up.values()["bust_circ"] == pytest.approx(920.0)  # 2 cm in a file in millimetres
    assert down.values()["height"] == pytest.approx(1610.0)
    assert up.values()["half_bust"] == pytest.approx(460.0)  # a formula follows its measurement
    with pytest.raises(MeasurementError, match="only a person"):
        nudged_tables(MULTI)


def test_with_the_table_every_measurement_moves_half_a_size_step() -> None:
    from yoko_engine.binding import nudged_tables

    person = individual_table(MULTI.values())
    own = person.values()
    up, down = (t.values() for t in nudged_tables(person, MULTI))
    assert up["bust_circ"] - own["bust_circ"] == pytest.approx(2.0)  # half of the 4 cm a size adds
    assert own["waist_circ"] - down["waist_circ"] == pytest.approx(2.0)
    assert up["height_waist_side_to_knee"] - own["height_waist_side_to_knee"] == pytest.approx(0.25)
    assert up["height"] - own["height"] == pytest.approx(3.0)  # the table does not grade height
    graded = size_grid(BASE, person, grading=MULTI)
    assert graded[1].values["height_waist_side_to_knee"] == up["height_waist_side_to_knee"]


def test_rebinding_changes_only_the_file_name() -> None:
    bound = rebind_measurements(BASE, "person.smis")
    assert bound.measurements_file == "person.smis"
    assert write_pattern(bound).count(b"<measurements>person.smis</measurements>") == 1


@pytest.mark.skipif(not SEAMLY2D.exists(), reason="the local Seamly2D build is not here")
def test_seamly2d_computes_the_basic_set_from_a_persons_file_like_the_engine() -> None:
    values = MULTI.values(40, 164)
    work = Path(tempfile.mkdtemp())
    (work / "person.smis").write_bytes(individual_measurements_file(values))
    (work / "style.sm2d").write_bytes(write_pattern(rebind_measurements(BASE, "person.smis")))
    env = dict(
        os.environ,
        HOME=str(work),
        QT_QPA_PLATFORM="offscreen",
        YOKO_ORACLE_DUMP=str(work / "o.json"),
    )
    done = subprocess.run(
        [str(SEAMLY2D), "--test", str(work / "style.sm2d")],
        env=env,
        capture_output=True,
        timeout=180,
        check=False,
    )
    assert done.returncode == 0
    oracle = json.loads((work / "o.json").read_text())
    ev = evaluate(BASE, values)
    wrong = [
        o["name"]
        for o in oracle["points"]
        if o["id"] in ev.points
        and (ev.points[o["id"]].p.x, ev.points[o["id"]].p.y) != (o["x_px"], o["y_px"])
    ]
    assert wrong == [] and len(oracle["points"]) >= 300
    shutil.rmtree(work)
