#!/usr/bin/env python3
"""Emit a safe one-row MySQL insert test using the first row in a dump.

The real table is never modified. A TEMPORARY TABLE is created with LIKE,
and the first tuple from the first INSERT statement is inserted into it.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterator


def chars_from_file(path: Path, chunk_size: int = 1024 * 1024) -> Iterator[str]:
    with path.open("r", encoding="utf-8", errors="surrogateescape", newline="") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                return
            yield from chunk


def find_insert_prefix_and_stream(path: Path) -> tuple[str, Iterator[str]]:
    """Return text through VALUES and a char stream beginning immediately after it."""
    pattern = re.compile(r"\bINSERT\s+INTO\b", re.IGNORECASE)
    values_pattern = re.compile(r"\bVALUES\b", re.IGNORECASE)

    f = path.open("r", encoding="utf-8", errors="surrogateescape", newline="")
    buffer = ""
    found_insert = False

    def remainder_stream(initial: str) -> Iterator[str]:
        try:
            yield from initial
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                yield from chunk
        finally:
            f.close()

    while True:
        chunk = f.read(1024 * 1024)
        if not chunk:
            f.close()
            raise ValueError(f"No INSERT INTO statement found in {path}")
        buffer += chunk

        if not found_insert:
            match = pattern.search(buffer)
            if not match:
                # Keep enough tail to catch a token split across chunks.
                buffer = buffer[-64:]
                continue
            buffer = buffer[match.start():]
            found_insert = True

        match = values_pattern.search(buffer)
        if match:
            prefix = buffer[:match.end()]
            remainder = buffer[match.end():]
            return prefix, remainder_stream(remainder)

        # INSERT headers are tiny; protect against a malformed file.
        if len(buffer) > 1024 * 1024:
            f.close()
            raise ValueError(f"Could not find VALUES after first INSERT INTO in {path}")


def extract_columns(prefix: str, expected_table: str) -> str:
    """Extract the optional `(col, ...)` clause between table and VALUES."""
    match = re.search(
        r"\bINSERT\s+INTO\s+`?([^`\s(]+)`?\s*(.*?)\s*\bVALUES\s*$",
        prefix,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise ValueError("Could not parse INSERT header")

    actual_table = match.group(1)
    if actual_table != expected_table:
        raise ValueError(
            f"First INSERT targets {actual_table!r}, expected {expected_table!r}"
        )

    columns = match.group(2).strip()
    if columns and not (columns.startswith("(") and columns.endswith(")")):
        raise ValueError(f"Unexpected INSERT column clause: {columns[:120]!r}")
    return columns


def extract_first_tuple(stream: Iterator[str]) -> str:
    started = False
    depth = 0
    in_single = False
    in_double = False
    escaped = False
    out: list[str] = []

    for ch in stream:
        if not started:
            if ch.isspace():
                continue
            if ch != "(":
                raise ValueError(f"Expected first VALUES tuple to start with '(', got {ch!r}")
            started = True
            depth = 1
            out.append(ch)
            continue

        out.append(ch)

        if escaped:
            escaped = False
            continue

        if (in_single or in_double) and ch == "\\":
            escaped = True
            continue

        if in_single:
            if ch == "'":
                in_single = False
            continue

        if in_double:
            if ch == '"':
                in_double = False
            continue

        if ch == "'":
            in_single = True
            continue
        if ch == '"':
            in_double = True
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return "".join(out)

    raise ValueError("INSERT ended before the first VALUES tuple was complete")


def quote_identifier(value: str) -> str:
    return "`" + value.replace("`", "``") + "`"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dump", type=Path)
    parser.add_argument("table")
    args = parser.parse_args()

    try:
        prefix, stream = find_insert_prefix_and_stream(args.dump)
        columns = extract_columns(prefix, args.table)
        row = extract_first_tuple(stream)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    temp_table = f"__insert_test_{args.table}"
    real_q = quote_identifier(args.table)
    temp_q = quote_identifier(temp_table)
    column_sql = f" {columns}" if columns else ""

    print("START TRANSACTION;")
    print(f"CREATE TEMPORARY TABLE {temp_q} LIKE {real_q};")
    print(f"INSERT INTO {temp_q}{column_sql} VALUES")
    print(f"{row};")
    print(f"SELECT COUNT(*) AS inserted_rows FROM {temp_q};")
    print("ROLLBACK;")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
