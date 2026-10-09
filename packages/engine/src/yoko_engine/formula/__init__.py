"""Seamly2D's formula language: parse once to an AST, evaluate against named values.

>>> from yoko_engine.formula import parse
>>> parse("size>14?1.5:1").evaluate({"size": 16.0})
1.5
"""

from yoko_engine.formula.errors import FormulaError, FormulaErrorCode
from yoko_engine.formula.formula import Formula, parse
from yoko_engine.formula.functions import CONSTANTS, FUNCTIONS

__all__ = ["CONSTANTS", "FUNCTIONS", "Formula", "FormulaError", "FormulaErrorCode", "parse"]
