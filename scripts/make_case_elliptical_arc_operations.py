"""Write fixtures/patterns/cases/elliptical_arc_operations.sm2d: elliptical arcs that are rotated,
mirrored (by line and by axis) and moved, also one operation after another (the transform of a
copy is built on the transform of the copy before it). The oracle computes it
(scripts/oracle_cases.sh).

    uv run python scripts/make_case_elliptical_arc_operations.py
"""

from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "fixtures/patterns/cases/elliptical_arc_operations.sm2d"

points = [(1, 10, 10), (2, 22, 14), (3, 27, 31), (4, 4, 28)]
arcs = [
    (10, 3, 2, 0, 360, 0),
    (11, 4, 2.5, 30, 200, 0),
    (12, 3, 5, 45, 135, 30),
    (13, 5, 3, 270, 90, 77),
    (14, 2.5, 6, 10, 350, 200),
]
lines = [
    f'            <point id="{i}" mx="0.132292" my="0.264583" name="P{i}" type="single" x="{x}" y="{y}"/>'
    for i, x, y in points
]
lines += [
    f'            <elArc angle1="{a1}" angle2="{a2}" center="1" color="black" id="{i}" lineWeight="1"'
    f' penStyle="solidLine" radius1="{r1}" radius2="{r2}" rotationAngle="{rot}" type="simple"/>'
    for i, r1, r2, a1, a2, rot in arcs
]
next_id = 100


def operation(attrs: str, sources: list[int]) -> list[int]:
    """One operation over `sources`; returns the ids of its copies."""
    global next_id
    op_id = next_id
    dests = list(range(op_id + 1, op_id + 1 + len(sources)))
    next_id = dests[-1] + 1
    items = "\n".join(
        f'                    <item alias="" color="black" idObject="{s}" lineType="solidLine"/>'
        for s in sources
    )
    outs = "\n".join(f'                    <item idObject="{d}"/>' for d in dests)
    lines.append(
        f'            <operation id="{op_id}" {attrs}>\n                <source>\n{items}\n'
        f"                </source>\n                <destination>\n{outs}\n"
        "                </destination>\n            </operation>"
    )
    return dests


originals = [a[0] for a in arcs]
rotated = operation('angle="30" center="2" suffix="_r1" type="rotation"', originals)
rotated2 = operation('angle="123.4" center="3" suffix="_r2" type="rotation"', originals[:3])
mirrored = operation('p1Line="2" p2Line="3" suffix="_ml" type="flippingByLine"', originals)
mirrored_again = operation('p1Line="4" p2Line="2" suffix="_ml2" type="flippingByLine"', mirrored)
operation('axisType="1" center="2" suffix="_ma1" type="flippingByAxis"', originals)
operation('axisType="2" center="3" suffix="_ma2" type="flippingByAxis"', originals)
moved = operation(
    'angle="343.68" center="0" length="17.8107" rotationAngle="90.0001" suffix="_m1" type="moving"',
    originals,
)
operation(
    'angle="20" center="1" length="5" rotationAngle="45" suffix="_m2" type="moving"', rotated2
)
operation('angle="100" center="0" length="3" rotationAngle="0" suffix="_m3" type="moving"', moved)
operation('angle="270" center="4" suffix="_r3" type="rotation"', mirrored_again)
operation('angle="15" center="1" suffix="_r4" type="rotation"', rotated)

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
print(f"wrote {OUT}")
