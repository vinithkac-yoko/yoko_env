"""Write fixtures/patterns/cases/spline_length_modes.sm2d: splines and cubic Beziers with every
combination of `autoSmooth` and `lengthMode`, for the oracle to compute (scripts/oracle_cases.sh).

    uv run python scripts/make_case_spline_length_modes.py
"""

from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "fixtures/patterns/cases/spline_length_modes.sm2d"

points = [(1, 0, 0), (2, 20, 5), (3, 35, -10), (4, 5, 25), (5, 30, 30), (6, -10, 15)]
controls = [
    (1070, 40, -5),
    (1071, 48, 5),
    (1072, 60, 25),
    (1073, 38, 40),
    (1074, 10, -5),
    (1075, 55, 12),
]
lines = [
    f'            <point id="{i}" mx="0.132292" my="0.264583" name="P{i}" type="single" x="{x}" y="{y}"/>'
    for i, x, y in points
]
lines += [
    f'            <point id="{i}" mx="0.132292" my="0.264583" name="C{i}" type="single" x="{x}" y="{y}"/>'
    for i, x, y in controls
]
next_id = 10


def options(auto: bool, mode: int, target: float | None) -> str:
    out = ' autoSmooth="true"' if auto else ""
    if mode:
        out += f' lengthMode="{mode}" length="{target}"'
    return out


geometries = [
    (1, 2, 40, 160, 4, 3.5),
    (1, 3, 10, 200, 6, 6),
    (4, 5, 300, 100, 5, 2),
    (6, 5, 80, 250, 3, 3),
    (1, 5, 45, 135, 12, 12),
]
for a, b, an1, an2, l1, l2 in geometries:
    for auto in (False, True):
        for mode in (0, 1, 2, 3):
            for target in [None] if mode == 0 else [8.0, 30.0, 0.5]:
                lines.append(
                    f'            <spline angle1="{an1}" angle2="{an2}" color="black" id="{next_id}"'
                    f' length1="{l1}" length2="{l2}" lineWeight="1" penStyle="solidLine"'
                    f' point1="{a}" point4="{b}" type="simpleInteractive"'
                    f"{options(auto, mode, target)}/>"
                )
                next_id += 1
beziers = [(1, 1070, 1071, 2), (1, 1072, 1073, 3), (4, 1074, 1075, 5), (1, 1071, 1072, 5)]
for a, c1, c2, b in beziers:
    for auto in (False, True):
        for mode in (0, 1, 2, 3):
            for target in [None] if mode == 0 else [10.0, 40.0]:
                lines.append(
                    f'            <spline color="black" id="{next_id}" lineWeight="1"'
                    f' penStyle="solidLine" point1="{a}" point2="{c1}" point3="{c2}" point4="{b}"'
                    f' type="cubicBezier"{options(auto, mode, target)}/>'
                )
                next_id += 1

body = "\n".join(lines)
OUT.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<pattern>
    <!--Pattern created with Seamly2D v2026.10.5.154 (https://seamly.io).-->
    <version>0.7.5</version>
    <unit>cm</unit>
    <description/>
    <notes/>
    <patternLabel/>
    <measurements/>
    <variables/>
    <draftBlock name="Pattern piece 1">
        <calculation>
{body}
        </calculation>
        <modeling/>
        <pieces/>
        <groups/>
    </draftBlock>
</pattern>
""")
print(f"wrote {OUT} with {next_id - 10} curves")
