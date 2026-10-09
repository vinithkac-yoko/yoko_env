"""Formula errors.

Codes mirror Seamly2D's `qmu::EErrorCodes` (src/libs/qmuparser/qmuparsererror.h), so a failure in
our parser maps to the same class of failure in Seamly2D. The three `TOO_*` / `UNDEFINED_*` codes at
the bottom are ours: they exist for the robustness caps (Addendum 1 §14) and for missing names.
"""

from __future__ import annotations

from enum import StrEnum


class FormulaErrorCode(StrEnum):
    UNEXPECTED_OPERATOR = "unexpected_operator"  # ecUNEXPECTED_OPERATOR
    UNASSIGNABLE_TOKEN = "unassignable_token"  # ecUNASSIGNABLE_TOKEN (also: undefined name)
    UNEXPECTED_EOF = "unexpected_eof"  # ecUNEXPECTED_EOF (also: empty formula)
    UNEXPECTED_ARG_SEP = "unexpected_arg_sep"  # ecUNEXPECTED_ARG_SEP
    UNEXPECTED_ARG = "unexpected_arg"  # ecUNEXPECTED_ARG
    UNEXPECTED_VAL = "unexpected_val"  # ecUNEXPECTED_VAL
    UNEXPECTED_VAR = "unexpected_var"  # ecUNEXPECTED_VAR
    UNEXPECTED_PARENS = "unexpected_parens"  # ecUNEXPECTED_PARENS
    UNEXPECTED_FUN = "unexpected_fun"  # ecUNEXPECTED_FUN
    TOO_MANY_PARAMS = "too_many_params"  # ecTOO_MANY_PARAMS
    TOO_FEW_PARAMS = "too_few_params"  # ecTOO_FEW_PARAMS
    UNEXPECTED_CONDITIONAL = "unexpected_conditional"  # ecUNEXPECTED_CONDITIONAL
    MISSING_ELSE_CLAUSE = "missing_else_clause"  # ecMISSING_ELSE_CLAUSE
    MISPLACED_COLON = "misplaced_colon"  # ecMISPLACED_COLON
    # Ours:
    TOO_LONG = "too_long"
    TOO_DEEP = "too_deep"
    UNDEFINED_NAME = "undefined_name"


class FormulaError(Exception):
    """A formula could not be parsed or evaluated.

    `position` is a 0-based character offset into `formula`, or None when not applicable.
    `hint` tells a model (or a person) what to try instead.
    """

    def __init__(
        self,
        code: FormulaErrorCode,
        message: str,
        formula: str,
        position: int | None = None,
        token: str | None = None,
        hint: str | None = None,
    ) -> None:
        super().__init__(code, message, formula, position, token, hint)
        self.code = code
        self.message = message
        self.formula = formula
        self.position = position
        self.token = token
        self.hint = hint

    def __str__(self) -> str:
        where = f" at {self.position}" if self.position is not None else ""
        return f"{self.code.value}: {self.message}{where} in {self.formula!r}"
