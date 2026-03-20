"""
sql_column_extractor.py — extract column references from simple SELECT queries.

Usage:
  python sql_column_extractor.py 'SELECT a, b FROM foo WHERE c = 1'
  echo 'SELECT ...' | python sql_column_extractor.py

Tests:
  python -m unittest sql_column_extractor
"""
from __future__ import annotations

import unittest
from dataclasses import dataclass, field

import sqlparse
from sqlparse.sql import Identifier, IdentifierList, Where, Comparison
from sqlparse.tokens import Keyword, DML, Wildcard, Name


def _unquote(name: str) -> str:
    """Strip SQL quoting characters."""
    return name.strip('"`[]')


def _column_name(ident: Identifier) -> str | None:
    """Extract the real column name from an Identifier, or None for non-columns."""
    name = ident.get_real_name()
    return _unquote(name) if name else None


@dataclass
class ExtractedColumns:
    table: str
    select_columns: list[str] = field(default_factory=list)
    where_columns: list[str] = field(default_factory=list)

    @property
    def all_columns(self) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for col in self.select_columns + self.where_columns:
            if col not in seen:
                seen.add(col)
                out.append(col)
        return out


def extract_columns(sql: str) -> ExtractedColumns:
    """Extract table, SELECT columns, and WHERE columns from a simple query."""
    parsed = sqlparse.parse(sql)
    if not parsed:
        raise ValueError("Could not parse SQL.")
    stmt = parsed[0]
    if stmt.get_type() != "SELECT":
        raise ValueError(f"Expected SELECT, got: {stmt.get_type()}")

    table = _find_table(stmt)
    select_cols = _find_select_columns(stmt)
    where_cols = _find_where_columns(stmt)
    return ExtractedColumns(table, select_cols, where_cols)


def _find_table(stmt) -> str:
    from_seen = False
    for tok in stmt.tokens:
        if tok.ttype is Keyword and tok.normalized == "FROM":
            from_seen = True
        elif from_seen and not tok.is_whitespace:
            if isinstance(tok, Identifier):
                return _unquote(tok.get_real_name())
            if tok.ttype is Name:
                return str(tok)
            break
    raise ValueError("Could not find table name.")


def _find_select_columns(stmt) -> list[str]:
    cols: list[str] = []
    collecting = False
    for tok in stmt.tokens:
        if tok.ttype is DML and tok.normalized == "SELECT":
            collecting = True
        elif collecting:
            if tok.ttype is Keyword and tok.normalized == "FROM":
                break
            if tok.ttype is Wildcard:
                raise ValueError("SELECT * not supported.")
            for ident in _as_identifiers(tok):
                if str(ident).strip().endswith("*"):
                    raise ValueError("SELECT * not supported.")
                name = _column_name(ident)
                if name:
                    cols.append(name)
    return cols


def _find_where_columns(stmt) -> list[str]:
    cols: list[str] = []
    seen: set[str] = set()

    where = next((t for t in stmt.tokens if isinstance(t, Where)), None)
    if not where:
        return cols

    for tok in where.tokens:
        ident = None
        if isinstance(tok, Comparison) and isinstance(tok.left, Identifier):
            ident = tok.left
        elif isinstance(tok, Identifier):
            ident = tok

        if ident:
            name = _column_name(ident)
            if name and name not in seen:
                seen.add(name)
                cols.append(name)
    return cols


def _as_identifiers(tok) -> list[Identifier]:
    if isinstance(tok, IdentifierList):
        return [t for t in tok.get_identifiers() if isinstance(t, Identifier)]
    if isinstance(tok, Identifier):
        return [tok]
    return []


# ---------------------------------------------------------------------------
# Tests — run with: python -m unittest sql_column_extractor
# ---------------------------------------------------------------------------

class TestExtractColumns(unittest.TestCase):
    def _check(self, sql, table, select, where):
        r = extract_columns(sql)
        self.assertEqual(r.table, table)
        self.assertEqual(r.select_columns, select)
        self.assertEqual(r.where_columns, where)
        # all_columns is deduplicated select + where
        seen = set()
        expected_all = [c for c in select + where if not (c in seen or seen.add(c))]
        self.assertEqual(r.all_columns, expected_all)

    def test_simple(self):
        self._check(
            "SELECT id, name, email FROM users WHERE age = 30 AND city = 'NYC'",
            "users", ["id", "name", "email"], ["age", "city"],
        )

    def test_qualified_columns_and_alias(self):
        self._check(
            "SELECT u.id, u.name FROM users u WHERE u.active = 1",
            "users", ["id", "name"], ["active"],
        )

    def test_quoted_and_aliased(self):
        self._check(
            'SELECT "FirstName" AS first, "LastName" AS last FROM people WHERE "Age" >= 21',
            "people", ["FirstName", "LastName"], ["Age"],
        )

    def test_in_between_like(self):
        self._check(
            "SELECT a, b FROM t WHERE d IN (1,2) AND e BETWEEN 1 AND 9 AND f LIKE '%x'",
            "t", ["a", "b"], ["d", "e", "f"],
        )

    def test_is_not_null(self):
        self._check("SELECT id FROM orders WHERE status IS NOT NULL",
                     "orders", ["id"], ["status"])

    def test_no_where(self):
        self._check("SELECT a FROM tbl ORDER BY a", "tbl", ["a"], [])

    def test_schema_qualified_table(self):
        self._check("SELECT a FROM s.tbl WHERE c = 1", "tbl", ["a"], ["c"])

    def test_trailing_semicolon(self):
        self._check("SELECT a FROM t WHERE b = 1;", "t", ["a"], ["b"])

    def test_star_raises(self):
        with self.assertRaises(ValueError):
            extract_columns("SELECT * FROM users")

    def test_qualified_star_raises(self):
        with self.assertRaises(ValueError):
            extract_columns("SELECT t.* FROM users t")

    def test_non_select_raises(self):
        with self.assertRaises(ValueError):
            extract_columns("INSERT INTO t (a) VALUES (1)")

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            extract_columns("")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        sql = " ".join(sys.argv[1:])
    elif not sys.stdin.isatty():
        sql = sys.stdin.read()
    else:
        print("Usage: python sql_column_extractor.py 'SELECT ...'", file=sys.stderr)
        print("Tests: python -m unittest sql_column_extractor", file=sys.stderr)
        sys.exit(1)

    sql = sql.strip()
    if not sql:
        print("Error: empty input", file=sys.stderr)
        sys.exit(1)

    try:
        result = extract_columns(sql)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"table:   {result.table}")
    print(f"select:  {', '.join(result.select_columns)}")
    print(f"where:   {', '.join(result.where_columns)}")
    print(f"all:     {', '.join(result.all_columns)}")