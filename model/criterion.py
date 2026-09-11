"""Composite Search Criterion and the US7 parser.

`parse_criterion` lives here so search is unit-testable without the View.
"""

from __future__ import annotations

from datetime import datetime

from model.pir import PIR, ParseError, TYPE_NAMES, parse_datetime

TEXT_FIELDS = frozenset({"text", "description", "name", "address", "mobile"})
TIME_FIELDS = frozenset({"deadline", "start", "alarm"})
OPS = {"=": lambda a, b: a == b, "<": lambda a, b: a < b, ">": lambda a, b: a > b}


class Criterion:
    def matches(self, pir: PIR) -> bool:
        raise NotImplementedError


class TypeIs(Criterion):
    def __init__(self, type_name: str):
        name = type_name.casefold()
        if name not in TYPE_NAMES:
            raise ParseError(f"unknown type: {type_name}")
        self.type_name = name

    def matches(self, pir: PIR) -> bool:
        return pir.type_name == self.type_name


class Contains(Criterion):
    """Substring after str.casefold(). field is None for unqualified contains."""

    def __init__(self, field: str | None, needle: str):
        if field is None:
            self.field = None
        else:
            key = field.casefold()
            if key not in TEXT_FIELDS:
                raise ParseError(f"unknown text field: {field}")
            self.field = key
        self.needle = needle.casefold()

    def matches(self, pir: PIR) -> bool:
        if self.field is None:
            return any(self.needle in text.casefold() for text in pir.text_fields())
        value = pir.text_value(self.field)
        if value is None:
            return False
        return self.needle in value.casefold()


class TimeCompare(Criterion):
    def __init__(self, field: str, op: str, instant: datetime):
        key = field.casefold()
        if key not in TIME_FIELDS:
            raise ParseError(f"unknown time field: {field}")
        if op not in OPS:
            raise ParseError(f"unknown comparison: {op}")
        self.field = key
        self.op = op
        self.instant = instant

    def matches(self, pir: PIR) -> bool:
        values = pir.time_values(self.field)
        if not values:
            return False
        compare = OPS[self.op]
        return any(compare(value, self.instant) for value in values)


class And(Criterion):
    def __init__(self, left: Criterion, right: Criterion):
        self.left = left
        self.right = right

    def matches(self, pir: PIR) -> bool:
        return self.left.matches(pir) and self.right.matches(pir)


class Or(Criterion):
    def __init__(self, left: Criterion, right: Criterion):
        self.left = left
        self.right = right

    def matches(self, pir: PIR) -> bool:
        return self.left.matches(pir) or self.right.matches(pir)


class Not(Criterion):
    def __init__(self, inner: Criterion):
        self.inner = inner

    def matches(self, pir: PIR) -> bool:
        return not self.inner.matches(pir)


def parse_criterion(text: str) -> Criterion:
    if text is None or not str(text).strip():
        raise ParseError("search criterion is required")
    parser = _Parser(tokenize(text))
    tree = parser.parse_or()
    parser.expect("EOF")
    return tree


def tokenize(text: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if text.startswith("&&", i):
            tokens.append(("AND", "&&"))
            i += 2
            continue
        if text.startswith("||", i):
            tokens.append(("OR", "||"))
            i += 2
            continue
        if ch == "!":
            tokens.append(("NOT", "!"))
            i += 1
            continue
        if ch == "(":
            tokens.append(("LPAREN", "("))
            i += 1
            continue
        if ch == ")":
            tokens.append(("RPAREN", ")"))
            i += 1
            continue
        if ch in "<>=":
            tokens.append(("CMP", ch))
            i += 1
            continue
        if ch == '"':
            value, i = _read_string(text, i)
            tokens.append(("STRING", value))
            continue
        if ch.isalpha() or ch == "_":
            j = i + 1
            while j < n and (text[j].isalnum() or text[j] == "_"):
                j += 1
            word = text[i:j]
            if word.casefold() == "contains":
                tokens.append(("CONTAINS", word))
            else:
                tokens.append(("IDENT", word))
            i = j
            continue
        j = i + 1
        while j < n and not text[j].isspace() and text[j] not in "()!<>=" and not text.startswith("&&", j) and not text.startswith("||", j):
            j += 1
        tokens.append(("TIME", text[i:j]))
        i = j
    tokens.append(("EOF", ""))
    return tokens


def _read_string(text: str, start: int) -> tuple[str, int]:
    i = start + 1
    chars: list[str] = []
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\\":
            i += 1
            if i >= n:
                raise ParseError("unterminated string")
            escaped = text[i]
            if escaped == "n":
                chars.append("\n")
            else:
                chars.append(escaped)
            i += 1
            continue
        if ch == '"':
            return "".join(chars), i + 1
        chars.append(ch)
        i += 1
    raise ParseError("unterminated string")


class _Parser:
    def __init__(self, tokens: list[tuple[str, str]]):
        self.tokens = tokens
        self.index = 0

    def peek(self) -> tuple[str, str]:
        return self.tokens[self.index]

    def peek_kind(self) -> str:
        return self.peek()[0]

    def take(self) -> tuple[str, str]:
        token = self.peek()
        self.index += 1
        return token

    def expect(self, kind: str) -> tuple[str, str]:
        got = self.take()
        if got[0] != kind:
            raise ParseError(f"expected {kind}, got {got[1]!r}")
        return got

    def parse_or(self) -> Criterion:
        node = self.parse_and()
        while self.peek_kind() == "OR":
            self.take()
            node = Or(node, self.parse_and())
        return node

    def parse_and(self) -> Criterion:
        node = self.parse_not()
        while self.peek_kind() == "AND":
            self.take()
            node = And(node, self.parse_not())
        return node

    def parse_not(self) -> Criterion:
        if self.peek_kind() == "NOT":
            self.take()
            return Not(self.parse_not())
        return self.parse_primary()

    def parse_primary(self) -> Criterion:
        if self.peek_kind() == "LPAREN":
            self.take()
            node = self.parse_or()
            self.expect("RPAREN")
            return node
        return self.parse_atom()

    def parse_atom(self) -> Criterion:
        if self.peek_kind() == "CONTAINS":
            self.take()
            needle = self.expect("STRING")[1]
            return Contains(None, needle)
        kind, value = self.take()
        if kind != "IDENT":
            raise ParseError(f"unexpected token: {value!r}")
        field = value.casefold()
        nxt_kind, nxt_val = self.peek()
        if field == "type":
            cmp_kind, op = self.take()
            if cmp_kind != "CMP" or op != "=":
                raise ParseError("type comparison must use =")
            type_token = self.take()
            if type_token[0] != "IDENT":
                raise ParseError("expected a PIR type after type =")
            return TypeIs(type_token[1])
        if nxt_kind == "CONTAINS":
            self.take()
            needle = self.expect("STRING")[1]
            return Contains(field, needle)
        if nxt_kind == "CMP":
            op = self.take()[1]
            instant = self._parse_instant()
            return TimeCompare(field, op, instant)
        raise ParseError(f"unexpected token after {value!r}")

    def _parse_instant(self) -> datetime:
        kind, value = self.take()
        if kind in {"TIME", "IDENT", "STRING"}:
            try:
                return parse_datetime(value)
            except Exception as exc:
                raise ParseError(f"invalid datetime: {value}") from exc
        raise ParseError("expected a datetime")
