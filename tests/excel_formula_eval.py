"""A small evaluator for the Excel formulas NovaQ writes (B8, OD-B8-4 A: Python re-computation from the cells).

It reads the formula text from an openpyxl worksheet and computes it, so a test checks the formulas as written,
not a copy of their mathematics. Only the subset the reports use is supported: numbers, strings, same-sheet cell
references and ranges, + - * / ^, comparisons, parentheses, and IF, AND, FACT, SUM, ISNUMBER. Anything else
raises, so an unsupported formula cannot pass silently. This is not Excel: the owner's one-time check in Excel
is still required before the formulas are called tested in Excel.
"""

from __future__ import annotations

import math
import re
from typing import Any

from openpyxl.utils import column_index_from_string
from openpyxl.worksheet.worksheet import Worksheet

_TOKEN = re.compile(r'\s*(?:(?P<num>\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)|(?P<str>"[^"]*")|(?P<ref>\$?[A-Z]{1,3}\$?\d+)'
                    r'|(?P<name>[A-Z]+)(?=\()|(?P<op>>=|<=|<>|[-+*/^(),:=<>]))')


class FormulaError(ValueError):
    """The formula uses something this evaluator does not support, or cannot be computed."""


class _Parser:
    """Parses a formula into thunks (functions of no arguments), so IF evaluates only the branch it returns,
    as Excel does (=IF(TRUE,1,1/0) is 1)."""

    def __init__(self, text: str, sheet: Worksheet, evaluator: SheetEvaluator) -> None:
        self.tokens = self._tokenize(text)
        self.position = 0
        self.sheet = sheet
        self.evaluator = evaluator

    @staticmethod
    def _tokenize(text: str) -> list[tuple[str, str]]:
        tokens, index = [], 0
        while index < len(text):
            match = _TOKEN.match(text, index)
            if match is None or match.end() == index:
                if text[index:].strip() == "":
                    break
                raise FormulaError(f"Cannot read {text[index:]!r}")
            kind = match.lastgroup
            assert kind is not None
            tokens.append((kind, match.group(kind)))
            index = match.end()
        return tokens

    def peek(self) -> tuple[str, str] | None:
        return self.tokens[self.position] if self.position < len(self.tokens) else None

    def take(self, value: str | None = None) -> tuple[str, str]:
        token = self.peek()
        if token is None or (value is not None and token[1] != value):
            raise FormulaError(f"Expected {value!r}, found {token!r}")
        self.position += 1
        return token

    def parse(self) -> Any:
        thunk = self.comparison()
        if self.peek() is not None:
            raise FormulaError(f"Unexpected {self.peek()!r}")
        return thunk()

    def comparison(self):
        left = self.additive()
        token = self.peek()
        if token and token[0] == "op" and token[1] in (">=", "<=", "<>", "=", "<", ">"):
            self.take()
            right = self.additive()
            symbol = token[1]

            def compare():
                a, b = left(), right()
                if not _numbers(a, b):
                    raise FormulaError("Comparison of non-numbers")
                return {">=": a >= b, "<=": a <= b, "<>": a != b, "=": a == b, "<": a < b, ">": a > b}[symbol]
            return compare
        return left

    def _binary(self, symbols: str, operand):
        value = operand()
        while (token := self.peek()) and token[0] == "op" and token[1] in symbols and len(token[1]) == 1:
            self.take()
            right = operand()
            value = self._apply(token[1], value, right)
        return value

    @staticmethod
    def _apply(symbol: str, left, right):
        def run():
            a, b = left(), right()
            _require(a, b)
            if symbol == "+":
                return a + b
            if symbol == "-":
                return a - b
            if symbol == "*":
                return a * b
            if symbol == "/":
                if b == 0:
                    raise FormulaError("#DIV/0!")
                return a / b
            if a == 0 and b == 0:
                raise FormulaError("#NUM! (Excel's 0^0)")
            return a ** b
        return run

    def additive(self):
        return self._binary("+-", self.term)

    def term(self):
        return self._binary("*/", self.power)

    def power(self):
        return self._binary("^", self.unary)

    def unary(self):
        token = self.peek()
        if token and token == ("op", "-"):
            self.take()
            inner = self.unary()

            def negate():
                value = inner()
                _require(value)
                return -value
            return negate
        return self.primary()

    def primary(self):
        kind, text = self.take()
        if kind == "num":
            number = float(text)
            return lambda: number
        if kind == "str":
            return lambda: text[1:-1]
        if kind == "ref":
            reference = text.replace("$", "")
            return lambda: self.evaluator.value(reference)
        if kind == "name":
            return self.function(text)
        if text == "(":
            inner = self.comparison()
            self.take(")")
            return inner
        raise FormulaError(f"Unexpected {(kind, text)!r}")

    def function(self, name: str):
        self.take("(")
        if name == "SUM":
            start = self.take()[1]
            self.take(":")
            end = self.take()[1]
            self.take(")")
            return lambda: math.fsum(_number_or_zero(value) for value in self.evaluator.range_values(start, end))
        args = [self.comparison()]
        while (token := self.peek()) and token[1] == ",":
            self.take(",")
            args.append(self.comparison())
        self.take(")")
        if name == "IF" and len(args) == 3:
            condition, when_true, when_false = args
            return lambda: when_true() if condition() else when_false()
        if name == "AND":
            return lambda: all(arg() for arg in args)
        if name == "ISNUMBER" and len(args) == 1:
            return lambda: _numbers(args[0]())

        if name == "FACT" and len(args) == 1:
            def fact():
                value = args[0]()
                _require(value)
                if value < 0 or value > 170:
                    raise FormulaError("#NUM! (FACT)")
                return float(math.factorial(int(value)))
            return fact
        raise FormulaError(f"Unsupported function {name}")


def _numbers(*values: Any) -> bool:
    return all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values)


def _require(*values: Any) -> None:
    if not _numbers(*values):
        raise FormulaError("#VALUE! (arithmetic on text)")


def _number_or_zero(value: Any) -> float:
    return float(value) if _numbers(value) else 0.0


class SheetEvaluator:
    """Computes cells of one worksheet, formulas included; blank cells count as 0, as in Excel arithmetic."""

    def __init__(self, sheet: Worksheet) -> None:
        self.sheet = sheet
        self.cache: dict[str, Any] = {}

    def value(self, reference: str) -> Any:
        if reference not in self.cache:
            raw = self.sheet[reference].value
            if isinstance(raw, str) and raw.startswith("="):
                self.cache[reference] = _Parser(raw[1:], self.sheet, self).parse()
            else:
                self.cache[reference] = 0.0 if raw is None else raw
        return self.cache[reference]

    def range_values(self, start: str, end: str) -> list[Any]:
        first_col, first_row = _split(start)
        last_col, last_row = _split(end)
        return [self.value(f"{_letters(col)}{row}") for row in range(first_row, last_row + 1)
                for col in range(first_col, last_col + 1)]


def _split(reference: str) -> tuple[int, int]:
    match = re.fullmatch(r"([A-Z]{1,3})(\d+)", reference.replace("$", ""))
    if match is None:
        raise FormulaError(f"Bad reference {reference}")
    return column_index_from_string(match.group(1)), int(match.group(2))


def _letters(index: int) -> str:
    from openpyxl.utils import get_column_letter

    return get_column_letter(index)
