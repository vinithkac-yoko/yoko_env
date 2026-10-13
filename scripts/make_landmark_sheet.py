"""Build the landmark sheet for the pattern makers (docs/landmarks/basic-set-landmarks.xlsx).

One tab per piece of the basic set: a picture of the piece with numbered points, and a table with one
row per numbered point or curve (where it is, how Seamly2D drew it, our proposed name and why) and
empty columns for the pattern maker's verdict. Nothing proposed here is verified.

    uv run python scripts/make_landmark_sheet.py
"""

from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

import yaml
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XlImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

sys.path.insert(0, str(Path(__file__).resolve().parent))
from landmark_rows import piece_rows
from yoko_io.render import render_outline_png

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/landmarks/basic-set-landmarks.xlsx"
PROPOSED = ROOT / "docs/landmarks/proposed_names.yaml"

FONT = "Arial"
HEAD_FILL = PatternFill("solid", fgColor="1F2933")
INPUT_FILL = PatternFill("solid", fgColor="FFF2CC")  # cells the pattern maker fills in
GUESS_FILL = PatternFill("solid", fgColor="E8F0FE")
THIN = Side(style="thin", color="BFC5CC")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
COLUMNS = [
    ("No.", 6),
    ("Kind", 8),
    ("Seamly2D label", 18),
    ("How it was drawn", 38),
    ("Uses measurements", 24),
    ("x (mm)", 9),
    ("y (mm)", 9),
    ("Proposed name", 30),
    ("Confidence", 11),
    ("Why we think so", 46),
    ("Verdict", 14),
    ("Correct name (if Correct)", 30),
    ("Comment", 36),
]

GLOSSARY = [
    ("CB", "centre back"),
    ("CF", "centre front"),
    ("SNP", "side neck point: where the neckline meets the shoulder seam"),
    ("BP", "bust point (not on these pieces; reserved for bust-dart work)"),
    ("underarm", "the lowest point of the armhole, where it meets the side seam"),
    ("shoulder_tip", "the outer end of the shoulder seam, where the armhole begins"),
    ("side_waist / side_hip", "the point on the side seam at the waist line / hip line"),
    ("inseam", "the inside leg seam of a trouser"),
    ("cap_top", "the highest point of the sleeve cap"),
    ("dartN_leg_a / _leg_b / _fold / _tip", "the points that make up a dart; N numbers them"),
]


def style(cell, *, bold=False, color="000000", fill=None, wrap=True, size=10):
    cell.font = Font(name=FONT, size=size, bold=bold, color=color)
    cell.alignment = Alignment(wrap_text=wrap, vertical="top")
    if fill is not None:
        cell.fill = fill


def readme(ws) -> None:
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 26
    ws.column_dimensions["C"].width = 100
    rows = [
        ("Landmark sheet: basic pattern set", None, "title"),
        (
            "Why",
            "The software that drafts and checks patterns refers to points by meaningful names "
            "(bodice_front.shoulder_tip) instead of Seamly2D labels (C30). Labels are numbered in the "
            "order a point was drawn and change from pattern to pattern. We need your help to name the "
            "points that matter.",
            None,
        ),
        (
            "What is in it",
            "One tab per piece (7 pieces). Each tab has a picture of the piece with numbered circles, and "
            "a table with one row per number. A row is a corner point or a curve of the piece's outline.",
            None,
        ),
        (
            "What we ask",
            "For every row, in the yellow columns: choose a Verdict. Confirm = our proposed name is right. "
            "Correct = write the right name in 'Correct name'. Reject = this point does not need a "
            "name. Rows with no proposed name: write a name in 'Correct name' and choose Correct, or "
            "leave them empty if the point needs no name. Add anything in 'Comment'.",
            None,
        ),
        (
            "Nothing is verified",
            "All proposed names are guesses from how the point was drawn and where it sits. 'Confidence' "
            "says how sure we are: high = the formula itself names the thing (a hip point uses the hip "
            "measurement); medium = shape and position make it likely; low = a guess from shape alone. "
            "Please do not trust the names.",
            None,
        ),
        (
            "Naming",
            "<piece>.<landmark>, lower-case with underscores; common abbreviations in capitals "
            "(CB, CF, SNP). See the Glossary tab. If the usual name in your trade is different, write "
            "yours: we will use it.",
            None,
        ),
        (
            "Rows that repeat a label",
            "A curve that Seamly2D draws as one long object may appear in several rows (it is cut by the "
            "points between them). Name each row for the part of the outline it shows.",
            None,
        ),
        (
            "Positions",
            "x and y are millimetres on the drawing at the base size (UK 6, height 164 cm). y grows "
            "downward, as on screen. They are for orientation only.",
            None,
        ),
        ("Example row", None, "example"),
    ]
    r = 2
    for head, text, kind in rows:
        if kind == "title":
            ws.cell(row=r, column=2, value=head)
            style(ws.cell(row=r, column=2), bold=True, size=16, wrap=False)
            ws.row_dimensions[r].height = 28
        elif kind == "example":
            ws.cell(row=r, column=2, value=head)
            style(ws.cell(row=r, column=2), bold=True)
            r += 1
            for c, (h, _w) in enumerate(COLUMNS, start=1):
                cell = ws.cell(row=r, column=c + 1, value=h)
                style(cell, bold=True, color="FFFFFF", fill=HEAD_FILL)
            r += 1
            example = [
                "7",
                "point",
                "C30",
                "pointOfContact; radius=shoulder_length",
                "shoulder_length",
                "329.1",
                "74.2",
                "bodice_front.shoulder_tip",
                "medium",
                "end of the shoulder; radius is shoulder_length",
                "Confirm",
                "",
                "",
            ]
            for c, v in enumerate(example, start=1):
                cell = ws.cell(row=r, column=c + 1, value=v)
                style(cell, fill=INPUT_FILL if c >= 11 else None)
            ws.cell(row=r + 1, column=2, value="(This row is only an illustration of the format.)")
            style(ws.cell(row=r + 1, column=2), color="52606D", wrap=False)
            r += 1
        else:
            ws.cell(row=r, column=2, value=head)
            style(ws.cell(row=r, column=2), bold=True)
            ws.cell(row=r, column=3, value=text)
            style(ws.cell(row=r, column=3))
            ws.row_dimensions[r].height = max(30, 15 * (len(text or "") // 95 + 1))
        r += 1
    # the example table is wider than the columns used above: give them widths
    for c in range(4, len(COLUMNS) + 3):
        ws.column_dimensions[get_column_letter(c)].width = 20


def glossary(ws, names: dict[str, list[tuple[str, str]]]) -> None:
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 90
    ws["A1"] = "Abbreviations"
    style(ws["A1"], bold=True, size=14, wrap=False)
    r = 3
    for term, meaning in GLOSSARY:
        ws.cell(row=r, column=1, value=term)
        ws.cell(row=r, column=2, value=meaning)
        style(ws.cell(row=r, column=1), bold=True)
        style(ws.cell(row=r, column=2))
        r += 1
    r += 1
    ws.cell(row=r, column=1, value="All proposed names")
    style(ws.cell(row=r, column=1), bold=True, size=14, wrap=False)
    r += 2
    for piece, entries in names.items():
        ws.cell(row=r, column=1, value=piece)
        style(ws.cell(row=r, column=1), bold=True, fill=GUESS_FILL)
        ws.cell(row=r, column=2, value=", ".join(n for n, _ in entries))
        style(ws.cell(row=r, column=2), fill=GUESS_FILL)
        ws.row_dimensions[r].height = max(30, 14 * (len(ws.cell(row=r, column=2).value) // 85 + 1))
        r += 1


def piece_tab(ws, pr, proposals: dict[int, dict]) -> int:
    ws.sheet_view.showGridLines = False
    for c, (_h, w) in enumerate(COLUMNS, start=1):
        ws.column_dimensions[get_column_letter(c)].width = w
    ws["A1"] = pr.name
    style(ws["A1"], bold=True, size=14, wrap=False)
    ws["A2"] = (
        "Numbered circles on the picture match the 'No.' column. Fill the yellow columns "
        "(Verdict, Correct name, Comment)."
    )
    style(ws["A2"], color="52606D", wrap=False)
    png = render_outline_png(
        list(pr.outline_px), [(str(n), pt) for n, pt in pr.marks_px], width_px=900
    )
    img = XlImage(BytesIO(png))
    scale = min(1.0, 620 / img.height, 900 / img.width)
    img.width, img.height = int(img.width * scale), int(img.height * scale)
    ws.add_image(img, "A4")
    header_row = 4 + int(img.height / 20) + 3
    for c, (h, _w) in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=header_row, column=c, value=h)
        style(cell, bold=True, color="FFFFFF", fill=HEAD_FILL)
        cell.border = BORDER
    dv = DataValidation(type="list", formula1='"Confirm,Correct,Reject"', allow_blank=True)
    ws.add_data_validation(dv)
    for i, row in enumerate(pr.rows, start=1):
        r = header_row + i
        prop = proposals.get(row.number)
        values = [
            row.number,
            row.kind,
            row.label,
            row.tool + ("; " + row.how if row.how else ""),
            row.measurements,
            row.x_mm,
            row.y_mm,
            prop["name"] if prop else "",
            prop["confidence"] if prop else "",
            prop["reason"] if prop else "no proposal: please name it if it matters",
            None,
            None,
            None,
        ]
        for c, v in enumerate(values, start=1):
            cell = ws.cell(row=r, column=c, value=v)
            style(cell, fill=INPUT_FILL if c >= 11 else (GUESS_FILL if c in (8, 9, 10) else None))
            cell.border = BORDER
        dv.add(ws.cell(row=r, column=11))
    return header_row


def seam_pairs(ws, piece_names: list[str]) -> None:
    """A tab for the pattern makers to say which edges are sewn to which."""
    ws.sheet_view.showGridLines = False
    widths = [22, 12, 12, 22, 12, 12, 16, 40]
    for c, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(c)].width = w
    ws["A1"] = "Seam pairs: which edges are sewn together"
    style(ws["A1"], bold=True, size=14, wrap=False)
    ws["A2"] = (
        "One row per seam. Use the numbers from the piece tabs ('No.' column): an edge runs from one "
        "numbered corner to the next. Say if the two edges should be the same length, or by how much "
        "one is longer (ease). Leave the yellow cells empty for seams you are not sure about."
    )
    style(ws["A2"], color="52606D")
    ws.merge_cells("A2:H2")
    ws.row_dimensions[2].height = 48
    heads = [
        "First piece", "Edge from No.", "Edge to No.", "Second piece", "Edge from No.", "Edge to No.",
        "Same length?", "Comment (ease, notches, anything)",
    ]  # fmt: skip
    for c, h in enumerate(heads, start=1):
        style(ws.cell(row=4, column=c, value=h), bold=True, color="FFFFFF", fill=HEAD_FILL)
    example = [
        "C - Bodice Front",
        12,
        15,
        "C - Bodice Back",
        9,
        6,
        "Yes",
        "Example row: please overwrite",
    ]
    for c, v in enumerate(example, start=1):
        cell = ws.cell(row=5, column=c, value=v)
        style(cell, color="9AA5B1")
        cell.border = BORDER
    pieces = DataValidation(
        type="list", formula1='"' + ",".join(piece_names) + '"', allow_blank=True
    )
    same = DataValidation(type="list", formula1='"Yes,No,Ease"', allow_blank=True)
    ws.add_data_validation(pieces)
    ws.add_data_validation(same)
    for r in range(6, 36):
        for c in range(1, 9):
            cell = ws.cell(row=r, column=c)
            style(cell, fill=INPUT_FILL)
            cell.border = BORDER
        pieces.add(ws.cell(row=r, column=1))
        pieces.add(ws.cell(row=r, column=4))
        same.add(ws.cell(row=r, column=7))


def main() -> None:
    proposed = yaml.safe_load(PROPOSED.read_text())["pieces"]
    wb = Workbook()
    readme(wb.active)
    wb.active.title = "Read me"
    names: dict[str, list[tuple[str, str]]] = {}
    for pr in piece_rows():
        entries = proposed.get(pr.name, {})
        for number, e in entries.items():
            row = next((r for r in pr.rows if r.number == number), None)
            if row is None or row.label != e["label"]:
                raise SystemExit(
                    f"{pr.name} row {number}: proposal is for {e['label']}, "
                    f"the piece has {row.label if row else 'nothing'} there"
                )
        names[pr.name] = [(e["name"], e["confidence"]) for _, e in sorted(entries.items())]
        ws = wb.create_sheet(pr.name[:31])
        piece_tab(ws, pr, entries)
    gl = wb.create_sheet("Glossary", 1)
    glossary(gl, names)
    seam_pairs(wb.create_sheet("Seam pairs", 2), list(names))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
