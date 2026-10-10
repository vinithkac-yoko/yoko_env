"""Tokenizer and parser for Seamly2D formulas.

Ported from Seamly2D's muparser fork (src/libs/qmuparser):
- token order and rules: qmuparsertokenreader.cpp (`ReadNextToken`, `IsBuiltIn`, `IsFunTok`,
  `IsValTok`)
- precedence and associativity: qmuparserbase.cpp (`GetOprtPrecedence`, `GetOprtAssociativity`,
  `CreateRPN`) and qmuparserdef.h (`EOprtPrecedence`)
- number syntax: qmudef.cpp (`ReadVal`)
- identifier characters: qmuformulabase.cpp (`InitCharSets`)
- evaluation-locale separators (`;` between arguments, `.` decimal): qmuformulabase.cpp
  (`SetSepForEval`)

Precedence, lowest to highest: `?:`, `||`, `&&`, comparisons (all six, left associative), `+ -`,
`* /`, unary minus, `^` (right associative). Unary minus binds looser than `^` (so `-2^2` is -4) and
is Seamly2D's only prefix operator: `+5` and `--5` are errors.

Known differences from Seamly2D, listed in docs/formula-differences.md:
- A comma is rejected. Seamly2D's evaluation locale treats `,` as a thousands separator.
- Identifier letters: any Unicode letter, where Seamly2D accepts a fixed list of alphabets.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from yoko_engine.formula.ast import Binary, Call, Name, Neg, Node, Num, Ternary
from yoko_engine.formula.errors import FormulaError, FormulaErrorCode
from yoko_engine.formula.functions import CONSTANTS, FUNCTIONS

MAX_FORMULA_LENGTH: Final = 1000
MAX_TOKENS: Final = 300
MAX_NESTING: Final = 40

# c_DefaultOprt order matters: longer operators first (qmuparserbase.cpp).
_OPERATORS: Final = ("<=", ">=", "!=", "==", "<", ">", "+", "-", "*", "/", "^", "&&", "||", "=")
_CMP: Final = frozenset({"<", ">", "<=", ">=", "==", "!="})
_EXTRA_NAME_CHARS: Final = frozenset("_@#'°")


def _is_name_char(ch: str) -> bool:
    return ch.isalnum() or ch in _EXTRA_NAME_CHARS


def is_valid_name(name: str) -> bool:
    """Can `name` be used as a measurement or variable name in a formula? (No blanks or operators,
    and it does not start with a digit.)"""
    return bool(name) and not name[0].isdigit() and all(_is_name_char(c) for c in name)


@dataclass(frozen=True, slots=True)
class Token:
    kind: str  # num name func op ( ) ; ? : end
    text: str
    pos: int
    value: float = 0.0


def _fail(
    code: FormulaErrorCode,
    message: str,
    text: str,
    pos: int | None,
    token: str | None = None,
    hint: str | None = None,
) -> FormulaError:
    return FormulaError(code, message, text, pos, token, hint)


# Number reader: the state machine of ReadVal (qmudef.cpp), minus thousands separators.
_INIT, _MANT, _DOT, _ABS, _EXPMARK, _EXPSIGN, _EXP = range(7)


def read_number(text: str, pos: int) -> tuple[float, int] | None:
    """Read a number at `pos`. Returns (value, end) or None when there is no valid number.

    Like Seamly2D, a malformed number such as `5.` or `1e` is rejected as a whole.
    """
    state = _INIT
    i = pos
    n = len(text)
    while True:
        ch = text[i] if i < n else ""
        if ch.isascii() and ch.isdigit():
            kind = "digit"
        elif ch == ".":
            kind = "dot"
        elif ch in ("e", "E"):
            kind = "exp"
        elif ch in ("+", "-"):
            kind = "sign"
        else:
            kind = "none"

        done = False
        if state == _INIT:
            nxt = {"digit": _MANT, "dot": _DOT}.get(kind)
        elif state == _MANT:
            nxt = {"digit": _MANT, "dot": _DOT, "exp": _EXPMARK}.get(kind)
            done = kind in ("none", "sign")
        elif state == _DOT:
            nxt = _ABS if kind == "digit" else None
        elif state == _ABS:
            nxt = {"digit": _ABS, "exp": _EXPMARK}.get(kind)
            done = kind in ("none", "sign")
        elif state == _EXPMARK:
            nxt = {"sign": _EXPSIGN, "digit": _EXP}.get(kind)
        elif state == _EXPSIGN:
            nxt = _EXP if kind == "digit" else None
        else:  # _EXP
            nxt = _EXP if kind == "digit" else None
            done = kind in ("none", "exp")
        if done:
            return float(text[pos:i]), i
        if nxt is None:
            return None
        state = nxt
        i += 1


def tokenize(text: str) -> list[Token]:
    if len(text) > MAX_FORMULA_LENGTH:
        raise _fail(
            FormulaErrorCode.TOO_LONG,
            f"formula is longer than {MAX_FORMULA_LENGTH} characters",
            text[:60] + "...",
            None,
            hint="split the construction into several objects or use variables",
        )
    tokens: list[Token] = []
    i = 0
    n = len(text)
    while True:
        while i < n and text[i] <= " ":  # non-printable and blanks are skipped
            i += 1
        if i >= n:
            tokens.append(Token("end", "", n))
            return tokens
        if len(tokens) > MAX_TOKENS:
            raise _fail(
                FormulaErrorCode.TOO_LONG,
                f"formula has more than {MAX_TOKENS} tokens",
                text[:60] + "...",
                i,
                hint="split the construction into several objects or use variables",
            )
        start = i
        j = i
        while j < n and _is_name_char(text[j]):
            j += 1
        word = text[i:j]
        # 1. function: a known name directly followed by '('
        if word in FUNCTIONS and j < n and text[j] == "(":
            tokens.append(Token("func", word, start))
            i = j
            continue
        # 2. built-in operators, longest first
        for op in _OPERATORS:
            if text.startswith(op, i):
                tokens.append(Token("op", op, start))
                i += len(op)
                break
        else:
            ch = text[i]
            if ch in "()?:;":
                tokens.append(Token(ch, ch, start))
                i += 1
            elif word in CONSTANTS:
                tokens.append(Token("num", word, start, CONSTANTS[word]))
                i = j
            else:
                num = read_number(text, i)
                if num is not None:
                    tokens.append(Token("num", text[i : num[1]], start, num[0]))
                    i = num[1]
                elif word:
                    tokens.append(Token("name", word, start))
                    i = j
                elif ch == ",":
                    raise _fail(
                        FormulaErrorCode.UNASSIGNABLE_TOKEN,
                        "',' is not allowed in a formula",
                        text,
                        i,
                        ",",
                        hint="separate function arguments with ';', and write decimals with '.'",
                    )
                else:
                    raise _fail(
                        FormulaErrorCode.UNASSIGNABLE_TOKEN,
                        f"unrecognised character {ch!r}",
                        text,
                        i,
                        ch,
                    )


class _Parser:
    def __init__(self, text: str) -> None:
        self.text = text
        self.tokens = tokenize(text)
        self.i = 0
        self.depth = 0

    # -- helpers ----------------------------------------------------------------------------
    @property
    def tok(self) -> Token:
        return self.tokens[self.i]

    def advance(self) -> Token:
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def error(
        self, code: FormulaErrorCode, message: str, tok: Token, hint: str | None = None
    ) -> FormulaError:
        return _fail(code, message, self.text, tok.pos, tok.text or None, hint)

    def unexpected(self, tok: Token) -> FormulaError:
        """Why `tok` cannot appear here (maps to Seamly2D's error codes)."""
        k = tok.kind
        if k == "end":
            return self.error(FormulaErrorCode.UNEXPECTED_EOF, "formula ends too early", tok)
        if k == "num":
            return self.error(FormulaErrorCode.UNEXPECTED_VAL, f"unexpected value {tok.text}", tok)
        if k == "name":
            return self.error(FormulaErrorCode.UNEXPECTED_VAR, f"unexpected name {tok.text}", tok)
        if k == "func":
            return self.error(
                FormulaErrorCode.UNEXPECTED_FUN, f"unexpected function {tok.text}", tok
            )
        if k in ("(", ")"):
            return self.error(FormulaErrorCode.UNEXPECTED_PARENS, f"unexpected {tok.text!r}", tok)
        if k == ";":
            return self.error(
                FormulaErrorCode.UNEXPECTED_ARG_SEP,
                "';' only separates function arguments",
                tok,
            )
        if k == "?":
            return self.error(FormulaErrorCode.UNEXPECTED_CONDITIONAL, "unexpected '?'", tok)
        if k == ":":
            return self.error(FormulaErrorCode.MISPLACED_COLON, "':' without a matching '?'", tok)
        hint = None
        if tok.text == "+":
            hint = "Seamly2D has no unary plus: remove the '+'"
        elif tok.text == "=":
            hint = "use '==' to compare; formulas cannot assign"
        return self.error(
            FormulaErrorCode.UNEXPECTED_OPERATOR, f"unexpected operator {tok.text!r}", tok, hint
        )

    def enter(self) -> None:
        self.depth += 1
        if self.depth > MAX_NESTING:
            raise _fail(
                FormulaErrorCode.TOO_DEEP,
                f"formula is nested more than {MAX_NESTING} levels deep",
                self.text,
                self.tok.pos,
            )

    def leave(self) -> None:
        self.depth -= 1

    # -- grammar ----------------------------------------------------------------------------
    def parse(self) -> Node:
        node = self.ternary()
        if self.tok.kind != "end":
            raise self.unexpected(self.tok)
        return node

    def ternary(self) -> Node:
        self.enter()
        cond = self.logical_or()
        if self.tok.kind == "?":
            q = self.advance()
            then = self.ternary()
            colon = self.tok
            if colon.kind != ":":
                if colon.kind == "end":
                    raise self.error(
                        FormulaErrorCode.MISSING_ELSE_CLAUSE,
                        "'?' without ':'",
                        colon,
                        hint="write cond ? a : b",
                    )
                raise self.unexpected(colon)
            self.advance()
            otherwise = self.ternary()
            cond = Ternary(cond, then, otherwise, q.pos)
        self.leave()
        return cond

    def _left_assoc(self, ops: frozenset[str], operand: Callable[[], Node]) -> Node:
        left = operand()
        while self.tok.kind == "op" and self.tok.text in ops:
            op = self.advance()
            left = Binary(op.text, left, operand(), op.pos)
        return left

    def logical_or(self) -> Node:
        return self._left_assoc(frozenset({"||"}), self.logical_and)

    def logical_and(self) -> Node:
        return self._left_assoc(frozenset({"&&"}), self.comparison)

    def comparison(self) -> Node:
        return self._left_assoc(_CMP, self.additive)

    def additive(self) -> Node:
        return self._left_assoc(frozenset({"+", "-"}), self.multiplicative)

    def multiplicative(self) -> Node:
        return self._left_assoc(frozenset({"*", "/"}), self.unary)

    def unary(self) -> Node:
        if self.tok.kind == "op" and self.tok.text == "-":
            minus = self.advance()
            if self.tok.kind == "op" and self.tok.text == "-":
                raise self.error(
                    FormulaErrorCode.UNEXPECTED_OPERATOR,
                    "two minus signs in a row",
                    self.tok,
                    hint="write -(-x) if you really mean it",
                )
            return Neg(self.power(), minus.pos)
        return self.power()

    def power(self) -> Node:
        base = self.primary()
        if self.tok.kind == "op" and self.tok.text == "^":
            op = self.advance()
            return Binary("^", base, self.exponent(), op.pos)  # right associative
        return base

    def exponent(self) -> Node:
        if self.tok.kind == "op" and self.tok.text == "-":
            minus = self.advance()
            if self.tok.kind == "op" and self.tok.text == "-":
                raise self.unexpected(self.tok)
            return Neg(self.power(), minus.pos)
        return self.power()

    def primary(self) -> Node:
        tok = self.tok
        if tok.kind == "num":
            self.advance()
            return Num(tok.value, tok.pos)
        if tok.kind == "name":
            self.advance()
            return Name(tok.text, tok.pos)
        if tok.kind == "(":
            self.advance()
            inner = self.ternary()
            if self.tok.kind == ";":
                raise self.error(
                    FormulaErrorCode.UNEXPECTED_ARG,
                    "';' outside a function call",
                    self.tok,
                )
            if self.tok.kind != ")":
                raise self.unexpected(self.tok)
            self.advance()
            return inner
        if tok.kind == "func":
            return self.call()
        raise self.unexpected(tok)

    def call(self) -> Node:
        func = self.advance()
        spec = FUNCTIONS[func.text]
        self.advance()  # '('
        args: list[Node] = []
        if self.tok.kind != ")":
            args.append(self.ternary())
            while self.tok.kind == ";":
                self.advance()
                args.append(self.ternary())
        if self.tok.kind != ")":
            raise self.unexpected(self.tok)
        close = self.advance()
        if len(args) < spec.min_args:
            raise _fail(
                FormulaErrorCode.TOO_FEW_PARAMS,
                f"{func.text}() needs at least {spec.min_args} argument(s), got {len(args)}",
                self.text,
                close.pos,
                func.text,
            )
        if spec.max_args is not None and len(args) > spec.max_args:
            raise _fail(
                FormulaErrorCode.TOO_MANY_PARAMS,
                f"{func.text}() takes {spec.max_args} argument(s), got {len(args)}",
                self.text,
                close.pos,
                func.text,
            )
        return Call(func.text, tuple(args), func.pos)


def parse_tree(text: str) -> Node:
    return _Parser(text).parse()
