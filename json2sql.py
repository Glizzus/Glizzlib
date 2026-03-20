#!/usr/bin/env python3
"""Convert JSON to SQL INSERT statements."""

import argparse
import json
import sys


def escape_value(value):
    """Escape a Python value for safe inclusion in a SQL statement."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (dict, list)):
        return "'" + json.dumps(value).replace("'", "''") + "'"
    return "'" + str(value).replace("'", "''") + "'"


def row_to_insert(table, row):
    """Generate an INSERT statement for a single row dict."""
    columns = ", ".join(row.keys())
    values = ", ".join(escape_value(v) for v in row.values())
    return f"INSERT INTO {table} ({columns}) VALUES ({values});"


def batch_insert(table, rows):
    """Generate a single multi-row INSERT statement."""
    columns = ", ".join(rows[0].keys())
    all_values = []
    for row in rows:
        vals = ", ".join(escape_value(v) for v in row.values())
        all_values.append(f"  ({vals})")
    joined = ",\n".join(all_values)
    return f"INSERT INTO {table} ({columns})\nVALUES\n{joined};"


def main():
    parser = argparse.ArgumentParser(description="Convert JSON to SQL INSERT statements.")
    parser.add_argument("table", help="target table name")
    parser.add_argument("infile", nargs="?", type=argparse.FileType("r"), default=sys.stdin,
                        help="JSON file to read (default: stdin)")
    parser.add_argument("-b", "--batch", action="store_true",
                        help="emit a single multi-row INSERT instead of one per row")
    args = parser.parse_args()

    data = json.load(args.infile)

    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list) or not data:
        print("Error: JSON must be an object or a non-empty array of objects.", file=sys.stderr)
        sys.exit(1)

    if args.batch:
        print(batch_insert(args.table, data))
    else:
        for row in data:
            print(row_to_insert(args.table, row))


import unittest


class TestJson2Sql(unittest.TestCase):

    # -- escape_value --

    def test_escape_null(self):
        self.assertEqual(escape_value(None), "NULL")

    def test_escape_bool_true(self):
        self.assertEqual(escape_value(True), "TRUE")

    def test_escape_bool_false(self):
        self.assertEqual(escape_value(False), "FALSE")

    def test_escape_int(self):
        self.assertEqual(escape_value(42), "42")

    def test_escape_float(self):
        self.assertEqual(escape_value(3.14), "3.14")

    def test_escape_string(self):
        self.assertEqual(escape_value("hello"), "'hello'")

    def test_escape_string_with_single_quote(self):
        self.assertEqual(escape_value("O'Brien"), "'O''Brien'")

    def test_escape_empty_string(self):
        self.assertEqual(escape_value(""), "''")

    def test_escape_dict(self):
        result = escape_value({"a": 1})
        self.assertEqual(result, "'{\"a\": 1}'")

    def test_escape_list(self):
        result = escape_value([1, 2])
        self.assertEqual(result, "'[1, 2]'")

    def test_escape_nested_with_quote(self):
        result = escape_value({"key": "it's"})
        self.assertIn("''", result)

    # -- row_to_insert --

    def test_single_row(self):
        sql = row_to_insert("users", {"id": 1, "name": "Alice"})
        self.assertEqual(sql, "INSERT INTO users (id, name) VALUES (1, 'Alice');")

    def test_single_row_with_null(self):
        sql = row_to_insert("t", {"a": None})
        self.assertEqual(sql, "INSERT INTO t (a) VALUES (NULL);")

    def test_single_row_bool_before_int(self):
        """bool is a subclass of int; make sure True doesn't become 1."""
        sql = row_to_insert("t", {"flag": True})
        self.assertIn("TRUE", sql)
        self.assertNotIn("1", sql)

    # -- batch_insert --

    def test_batch_two_rows(self):
        rows = [{"id": 1, "v": "a"}, {"id": 2, "v": "b"}]
        sql = batch_insert("t", rows)
        self.assertIn("INSERT INTO t (id, v)", sql)
        self.assertIn("(1, 'a')", sql)
        self.assertIn("(2, 'b')", sql)
        self.assertEqual(sql.count(";"), 1, "batch should produce exactly one statement")

    def test_batch_single_row(self):
        sql = batch_insert("t", [{"x": 1}])
        self.assertIn("VALUES", sql)
        self.assertIn("(1)", sql)

    # -- integration-style --

    def test_single_object_treated_as_array(self):
        """A bare JSON object should work the same as a one-element array."""
        row = {"id": 1}
        single = row_to_insert("t", row)
        self.assertTrue(single.startswith("INSERT INTO"))

    def test_special_characters_in_string(self):
        sql = row_to_insert("t", {"s": "line1\nline2\ttab"})
        self.assertIn("line1\nline2\ttab", sql)

    def test_large_number(self):
        sql = row_to_insert("t", {"n": 99999999999999})
        self.assertIn("99999999999999", sql)

    def test_float_precision(self):
        sql = row_to_insert("t", {"n": 0.1 + 0.2})
        self.assertIn("0.3", sql)


if __name__ == "__main__":
    main()
