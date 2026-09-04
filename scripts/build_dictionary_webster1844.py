#!/usr/bin/env python3

import argparse
import json
import re
from pathlib import Path

DEFAULT_INPUT = Path("exports/dictionary_webster1844.ndjson")
DEFAULT_OUTPUT = Path("json/dictionary_webster1844.json")
ALTERNATE_SEPARATOR = ", or "


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize the raw Webster 1844 NDJSON export into application JSON."
    )
    parser.add_argument("input", nargs="?", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("output", nargs="?", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()

def clean_content(content: str) -> str:
    return re.sub(
        r'\s+id="\{byuid\}_\d+"',
        "",
        content
    )

def transform(row: dict) -> dict:
    source_word = row.get("_word")
    pronounce = row.get("pronounce")
    content = clean_content(row.get("definition"))

    if not isinstance(source_word, str) or not source_word:
        raise ValueError(
            f"Invalid word for dictionary_webster1844_id="
            f"{row.get('dictionary_webster1844_id')}: {source_word!r}"
        )

    if not isinstance(pronounce, str) or not pronounce:
        raise ValueError(
            f"Invalid pronounce value for dictionary_webster1844_id="
            f"{row.get('dictionary_webster1844_id')}: {pronounce!r}"
        )

    if not isinstance(content, str):
        raise ValueError(
            f"Invalid definition for dictionary_webster1844_id="
            f"{row.get('dictionary_webster1844_id')}"
        )

    separator_count = source_word.count(ALTERNATE_SEPARATOR)

    if separator_count > 1:
        raise ValueError(
            f"Unexpected multiple alternate spellings for "
            f"dictionary_webster1844_id={row.get('dictionary_webster1844_id')}: "
            f"{source_word!r}"
        )

    if separator_count == 1:
        word, alternate_word = source_word.split(ALTERNATE_SEPARATOR, 1)
        word = word.strip()
        alternate_word = alternate_word.strip()

        if not word or not alternate_word:
            raise ValueError(
                f"Invalid alternate spelling for dictionary_webster1844_id="
                f"{row.get('dictionary_webster1844_id')}: {source_word!r}"
            )
    else:
        word = source_word.strip()
        alternate_word = None

    result = {
        "word": word,
    }

    if alternate_word is not None:
        result["alternate_words"] = [alternate_word]

    result["pronounce"] = pronounce
    result["content"] = content

    return result


def write_json_array(rows: list[dict], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", encoding="utf-8") as destination:
        destination.write("[\n")

        for index, row in enumerate(rows):
            if index:
                destination.write(",\n")

            json.dump(
                row,
                destination,
                ensure_ascii=False,
                separators=(",", ":"),
            )

        destination.write("\n]\n")


def main() -> None:
    args = parse_args()

    rows: list[dict] = []
    total_rows = 0
    alternate_rows = 0

    print(f"Reading {args.input}...", flush=True)

    with args.input.open("r", encoding="utf-8") as source:
        for line in source:
            line = line.strip()

            if not line:
                continue

            total_rows += 1
            transformed = transform(json.loads(line))

            if "alternate_words" in transformed:
                alternate_rows += 1

            rows.append(transformed)

            if total_rows % 5000 == 0:
                print(f"Processed {total_rows:,} source rows", flush=True)

    print("Alphabetizing...", flush=True)
    rows.sort(key=lambda row: row["word"].casefold())

    print(f"Writing {len(rows):,} entries to {args.output}...", flush=True)
    write_json_array(rows, args.output)

    print(f"Source rows:         {total_rows:,}")
    print(f"Dictionary entries:  {len(rows):,}")
    print(f"Alternate spellings: {alternate_rows:,}")
    print(f"Wrote:               {args.output}")


if __name__ == "__main__":
    main()
