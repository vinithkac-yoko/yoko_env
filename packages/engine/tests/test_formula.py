"""Formula language tests. Each group cites the Seamly2D source it is checking."""

from __future__ import annotations

import contextlib
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from yoko_engine.formula import FUNCTIONS, FormulaError, FormulaErrorCode, parse
from yoko_engine.formula.parser import read_number

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "fixtures/patterns/base/Aldrich-Womens-6th-Ed-Basic-Blocks.sm2d"


def ev(text: str, **values: float) -> float:
    return parse(text).evaluate(values)


def code(text: str) -> FormulaErrorCode:
    with pytest.raises(FormulaError) as info:
        parse(text)
    return info.value.code


# -- precedence and associativity: qmuparserbase.cpp GetOprtPrecedence / GetOprtAssociativity ----
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1+2*3", 7.0),
        ("(1+2)*3", 9.0),
        ("10-4-3", 3.0),  # left associative
        ("100/10/5", 2.0),
        ("2^3^2", 512.0),  # right associative
        ("-2^2", -4.0),  # unary minus binds looser than ^
        ("2^-2", 0.25),
        ("2^-3^2", 2.0**-9),
        ("-2*3", -6.0),
        ("2*-3", -6.0),
        ("2--3", 5.0),
        ("1+1<3", 1.0),  # arithmetic binds tighter than comparison
        ("1<2==1", 1.0),  # comparisons share one level, left to right: (1<2)==1
        ("1||0&&0", 1.0),  # && binds tighter than ||
        ("0&&1||1", 1.0),
        ("-(-5)", 5.0),
    ],
)
def test_precedence(text: str, expected: float) -> None:
    assert ev(text) == pytest.approx(expected)


# -- ternary: qmuparserbase.cpp ApplyIfElse, ParseCmdCodeBulk cmIF ----------------------------
def test_ternary_nested_chain_from_the_basic_set() -> None:
    f = "size>22?4.75:size>16?4.5:size>10?4.25:4"  # increment #CrotchCurveBack
    assert ev(f, size=6) == 4.0
    assert ev(f, size=12) == 4.25
    assert ev(f, size=18) == 4.5
    assert ev(f, size=24) == 4.75


def test_ternary_has_lowest_precedence() -> None:
    assert ev("1+1?2:3") == 2.0
    assert ev("0?1:2+3") == 5.0


def test_ternary_condition_is_fuzzy_zero() -> None:
    assert ev("1e-13?1:2") == 2.0
    assert ev("1e-11?1:2") == 1.0


def test_ternary_evaluates_one_branch() -> None:
    assert ev("1?2:1/0") == 2.0
    assert math.isinf(ev("0?2:1/0"))


def test_names_in_untaken_branch_must_still_exist() -> None:
    with pytest.raises(FormulaError) as info:
        ev("1?2:ghost")
    assert info.value.code is FormulaErrorCode.UNDEFINED_NAME


# -- comparisons: qmuparserbase.cpp cmEQ / cmNEQ use QmuFuzzyComparePossibleNulls --------------
def test_equality_is_fuzzy() -> None:
    assert ev("0.1+0.2==0.3") == 1.0
    assert ev("1e-13==0") == 1.0
    assert ev("1e-13!=0") == 0.0
    assert ev("1==2") == 0.0


def test_logic_truthiness() -> None:
    assert ev("2&&3") == 1.0
    assert ev("0&&3") == 0.0
    assert ev("0||0") == 0.0
    assert ev("0.5||0") == 1.0


# -- division and pow follow C++: no MUP_MATH_EXCEPTIONS -------------------------------------
def test_division_by_zero_is_ieee() -> None:
    assert ev("1/0") == math.inf
    assert ev("-1/0") == -math.inf
    assert math.isnan(ev("0/0"))


def test_pow_edge_cases() -> None:
    assert ev("2^0.5") == pytest.approx(math.sqrt(2))
    assert math.isnan(ev("(-8)^0.5"))
    assert ev("0^-1") == math.inf
    assert ev("10^400") == math.inf
    assert ev("(-10)^401") == -math.inf


# -- functions: qmuparser.cpp InitFun ---------------------------------------------------------
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("sin(0)", 0.0),
        ("cos(0)", 1.0),
        ("tan(0)", 0.0),
        ("sinD(90)", 1.0),
        ("cosD(180)", -1.0),
        ("tanD(45)", 1.0),
        ("asin(1)", math.pi / 2),
        ("acos(1)", 0.0),
        ("atan(1)", math.pi / 4),
        ("atan2(1;1)", math.pi / 4),
        ("asinD(1)", 90.0),
        ("acosD(0)", 90.0),
        ("atanD(1)", 45.0),
        ("degTorad(180)", math.pi),
        ("radTodeg(_pi)", 180.0),
        ("sinh(0)", 0.0),
        ("cosh(0)", 1.0),
        ("tanh(0)", 0.0),
        ("asinh(0)", 0.0),
        ("acosh(1)", 0.0),
        ("atanh(0)", 0.0),
        ("log2(8)", 3.0),
        ("log10(1000)", 3.0),
        ("log(1000)", 3.0),  # `log` is base 10
        ("ln(_e)", 1.0),
        ("exp(0)", 1.0),
        ("sqrt(9)", 3.0),
        ("sign(-4)", -1.0),
        ("sign(0)", 0.0),
        ("sign(2)", 1.0),
        ("rint(2.5)", 3.0),  # floor(v + 0.5): not banker's rounding
        ("rint(-2.5)", -2.0),
        ("rint(2.4)", 2.0),
        ("abs(-3)", 3.0),
        ("fmod(7;3)", 1.0),
        ("fmod(-7;3)", -1.0),
        ("sum(1;2;3)", 6.0),
        ("avg(1;2;6)", 3.0),
        ("min(4;2;9)", 2.0),
        ("max(4;2;9)", 9.0),
        ("min(5)", 5.0),
        ("_pi", math.pi),
        ("_e", math.e),
    ],
)
def test_functions_and_constants(text: str, expected: float) -> None:
    assert ev(text) == pytest.approx(expected, abs=1e-12)


def test_function_domain_errors_are_nan_or_inf_not_exceptions() -> None:
    assert math.isnan(ev("sqrt(-1)"))
    assert math.isnan(ev("asin(2)"))
    assert math.isnan(ev("acos(-2)"))
    assert ev("ln(0)") == -math.inf
    assert math.isnan(ev("ln(-1)"))
    assert math.isnan(ev("log10(-1)"))
    assert math.isnan(ev("fmod(1;0)"))
    assert ev("exp(1000)") == math.inf
    assert ev("sinh(1000)") == math.inf
    assert ev("sinh(-1000)") == -math.inf
    assert math.isnan(ev("atanh(2)"))
    assert ev("atanh(1)") == math.inf


def test_every_function_is_reachable() -> None:
    assert len(FUNCTIONS) == 35
    for name, spec in FUNCTIONS.items():
        args = ";".join(["0.5"] * spec.min_args)
        float(ev(f"{name}({args})"))


# -- numbers: qmudef.cpp ReadVal -----------------------------------------------------------------
@pytest.mark.parametrize(
    ("text", "value", "end"),
    [("12", 12.0, 2), ("1.5", 1.5, 3), (".5", 0.5, 2), ("2e3", 2000.0, 3), ("1.5E-2", 0.015, 6),
     ("3+4", 3.0, 1), ("3-4", 3.0, 1), ("7)", 7.0, 1)],
)  # fmt: skip
def test_read_number(text: str, value: float, end: int) -> None:
    assert read_number(text, 0) == (value, end)


@pytest.mark.parametrize("text", ["5.", "1e", "1e+", ".", "e5", "1e5.5", "abc"])
def test_read_number_rejects_malformed(text: str) -> None:
    assert read_number(text, 0) is None


def test_scientific_notation_in_a_formula() -> None:
    assert ev("1e1 +2.5e-1") == 10.25
    assert ev("2.5e-1*4") == 1.0


def test_sign_straight_after_exponent_digits_is_rejected_like_seamly2d() -> None:
    # ReadVal's table sends (Exponent, InputSign) to 0 (qmudef.cpp), so `2e3-1` does not read as a
    # number. `2e3` then becomes a name, which is undefined: an error either way.
    assert parse("2e3-1").names == ("2e3",)
    with pytest.raises(FormulaError) as info:
        ev("2e3-1")
    assert info.value.code is FormulaErrorCode.UNDEFINED_NAME
    assert ev("2e3 -1") == 1999.0


# -- names: qmuformulabase.cpp InitCharSets -------------------------------------------------------
def test_names_and_dependencies() -> None:
    f = parse("(waist_circ/4)+4*#CM + Line_A11_A13a/2 + #CM")
    assert f.names == ("waist_circ", "#CM", "Line_A11_A13a")
    assert f.evaluate({"waist_circ": 60.0, "#CM": 1.0, "Line_A11_A13a": 8.0}) == 24.0


def test_geometry_style_names() -> None:
    f = parse("AngleLine_A10_A10a-90+10")
    assert f.names == ("AngleLine_A10_A10a",)
    assert f.evaluate({"AngleLine_A10_A10a": 100.0}) == 20.0
    assert parse("SplPath_C11_D4+#BackBalance").names == ("SplPath_C11_D4", "#BackBalance")
    assert parse("CurrentLength/2").names == ("CurrentLength",)


def test_name_that_looks_like_a_function_without_parens_is_a_name() -> None:
    assert parse("sin+1").names == ("sin",)


def test_undefined_name_is_reported_with_position_and_hint() -> None:
    with pytest.raises(FormulaError) as info:
        ev("1+ghost")
    err = info.value
    assert err.code is FormulaErrorCode.UNDEFINED_NAME
    assert err.position == 2
    assert err.token == "ghost"
    assert err.hint
    assert "ghost" in str(err)


# -- syntax errors: qmuparsererror.h codes -----------------------------------------------------
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", FormulaErrorCode.UNEXPECTED_EOF),
        ("   ", FormulaErrorCode.UNEXPECTED_EOF),
        ("2+", FormulaErrorCode.UNEXPECTED_EOF),
        ("sin(", FormulaErrorCode.UNEXPECTED_EOF),
        ("(1+2", FormulaErrorCode.UNEXPECTED_EOF),
        ("1+*2", FormulaErrorCode.UNEXPECTED_OPERATOR),
        ("*2", FormulaErrorCode.UNEXPECTED_OPERATOR),
        ("+5", FormulaErrorCode.UNEXPECTED_OPERATOR),  # no unary plus in Seamly2D
        ("--5", FormulaErrorCode.UNEXPECTED_OPERATOR),  # no stacked infix minus
        ("a=1", FormulaErrorCode.UNEXPECTED_OPERATOR),  # assignment is not allowed
        ("(1;2)", FormulaErrorCode.UNEXPECTED_ARG),
        ("1;2", FormulaErrorCode.UNEXPECTED_ARG_SEP),
        ("1 2", FormulaErrorCode.UNEXPECTED_VAL),
        ("2(3)", FormulaErrorCode.UNEXPECTED_PARENS),
        ("1)", FormulaErrorCode.UNEXPECTED_PARENS),
        (")", FormulaErrorCode.UNEXPECTED_PARENS),
        ("a b", FormulaErrorCode.UNEXPECTED_VAR),
        ("1 sin(2)", FormulaErrorCode.UNEXPECTED_FUN),
        ("1?2", FormulaErrorCode.MISSING_ELSE_CLAUSE),
        ("1:2", FormulaErrorCode.MISPLACED_COLON),
        ("?1:2", FormulaErrorCode.UNEXPECTED_CONDITIONAL),
        ("sin()", FormulaErrorCode.TOO_FEW_PARAMS),
        ("max()", FormulaErrorCode.TOO_FEW_PARAMS),
        ("sin(1;2)", FormulaErrorCode.TOO_MANY_PARAMS),
        ("atan2(1)", FormulaErrorCode.TOO_FEW_PARAMS),
        ("sin (1)", FormulaErrorCode.UNEXPECTED_PARENS),  # needs '(' right after the name
        ("5.", FormulaErrorCode.UNASSIGNABLE_TOKEN),
        ("1,5", FormulaErrorCode.UNASSIGNABLE_TOKEN),
        ("a & b", FormulaErrorCode.UNASSIGNABLE_TOKEN),
        ("{1}", FormulaErrorCode.UNASSIGNABLE_TOKEN),
    ],
)
def test_syntax_error_codes(text: str, expected: FormulaErrorCode) -> None:
    assert code(text) is expected


def test_error_hints_for_common_model_mistakes() -> None:
    with pytest.raises(FormulaError) as plus:
        parse("+5")
    assert "unary plus" in (plus.value.hint or "")
    with pytest.raises(FormulaError) as comma:
        parse("max(1,2)")
    assert "';'" in (comma.value.hint or "")


# -- caps (Addendum 1 §14) --------------------------------------------------------------------
def test_length_cap() -> None:
    assert code("1+" * 600 + "1") is FormulaErrorCode.TOO_LONG


def test_token_cap() -> None:
    assert code("1+" * 200 + "1") is FormulaErrorCode.TOO_LONG


def test_nesting_cap() -> None:
    assert code("(" * 60 + "1" + ")" * 60) is FormulaErrorCode.TOO_DEEP
    assert ev("(" * 30 + "1" + ")" * 30) == 1.0


def test_long_but_legal_chain_evaluates() -> None:
    assert ev("1+" * 140 + "1") == 141.0


# -- the real file ----------------------------------------------------------------------------
FORMULA_ATTRS = {"length", "angle", "radius", "length1", "length2", "angle1", "angle2", "formula"}


def _fixture_formulas() -> list[str]:
    out: list[str] = []
    for el in ET.parse(BASE).getroot().iter():
        if el.tag in ("point", "line", "arc", "spline", "increment", "operation"):
            for key, val in el.attrib.items():
                if key in FORMULA_ATTRS:
                    out.append(val)
    return out


def test_every_formula_in_the_basic_set_parses() -> None:
    formulas = _fixture_formulas()
    assert len(formulas) > 300
    unique = set(formulas)
    names: set[str] = set()
    for text in unique:
        if not text.strip():
            continue
        names.update(parse(text).names)
    # measurements and variables the file uses, plus geometry references
    assert "bust_circ" in names
    assert "#CM" in names
    assert "CurrentLength" in names
    assert any(n.startswith("Line_") for n in names)
    assert any(n.startswith("AngleLine_") for n in names)


def test_basic_set_variables_evaluate_at_base_size() -> None:
    root = ET.parse(BASE).getroot()
    incs = {i.get("name", ""): i.get("formula", "") for i in root.iter("increment")}
    values: dict[str, float] = {"size": 6.0, "height": 166.0}
    for name in ("#BaseHeight", "#CM"):
        values[name] = parse(incs[name]).evaluate(values)
    assert values["#CM"] == 1.0
    for name in ("#CrotchCurveBack", "#CrotchCurveFront", "#ArmscyeIndentB", "#ShoulderTip"):
        values[name] = parse(incs[name]).evaluate(values)
    assert values["#CrotchCurveBack"] == 4.0
    assert values["#CrotchCurveFront"] == 2.75
    assert values["#ArmscyeIndentB"] == 2.25
    assert values["#ShoulderTip"] == 1.0


# -- properties -----------------------------------------------------------------------------------
@settings(max_examples=300, deadline=None)
@given(st.text(max_size=80))
def test_parser_only_ever_raises_formula_error(text: str) -> None:
    with contextlib.suppress(FormulaError):
        parse(text)


@settings(max_examples=200, deadline=None)
@given(
    st.floats(-1e6, 1e6, allow_nan=False, allow_infinity=False),
    st.floats(-1e6, 1e6, allow_nan=False, allow_infinity=False),
)
def test_arithmetic_matches_python(a: float, b: float) -> None:
    values = {"a": a, "b": b}
    assert parse("a+b").evaluate(values) == a + b
    assert parse("a-b").evaluate(values) == a - b
    assert parse("a*b").evaluate(values) == a * b
    assert parse("-a").evaluate(values) == -a
    assert parse("(a+b)*(a-b)").evaluate(values) == (a + b) * (a - b)
    assert parse("min(a;b)").evaluate(values) == min(a, b)
    assert parse("max(a;b)").evaluate(values) == max(a, b)
    assert parse("a<b").evaluate(values) == float(a < b)
