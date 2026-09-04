#!/usr/bin/env python3

import argparse
import json
from pathlib import Path

DEFAULT_INPUT = Path("exports/dictionary_webster1828.ndjson")
DEFAULT_OUTPUT = Path("json/dictionary_webster1828.json")

SUGGESTION_HEADING = "Did you mean one of these words?"
NO_RESULTS_TEXT = "No results found"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize the raw Webster 1828 NDJSON export into application JSON."
    )
    parser.add_argument("input", nargs="?", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("output", nargs="?", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def is_scraper_result(row: dict) -> tuple[bool, str | None]:
    heading = row.get("heading", "")

    if heading == SUGGESTION_HEADING:
        return True, "suggestion"

    if NO_RESULTS_TEXT in heading:
        return True, "no_results"

    return False, None


def transform(row: dict) -> dict:
    source_word = row.get("word")
    normalized_word = row.get("_word")
    content = row.get("content")

    if not isinstance(source_word, str) or not source_word:
        raise ValueError(f"Invalid source word for id={row.get('id')}: {source_word!r}")

    if not isinstance(normalized_word, str) or not normalized_word:
        raise ValueError(
            f"Invalid normalized word for id={row.get('id')}: {normalized_word!r}"
        )

    if not isinstance(content, str):
        raise ValueError(f"Invalid content for id={row.get('id')}")

    result = {
        "word": normalized_word,
    }

    if source_word != normalized_word:
        if "-" not in source_word or source_word.replace("-", "") != normalized_word:
            raise ValueError(
                f"Unexpected alternate spelling for id={row.get('id')}: "
                f"word={source_word!r}, _word={normalized_word!r}"
            )

        result["alternate_words"] = [source_word]

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
    skipped_suggestions = 0
    skipped_no_results = 0

    print(f"Reading {args.input}...", flush=True)

    with args.input.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            line = line.strip()

            if not line:
                continue

            total_rows += 1
            row = json.loads(line)

            skip, reason = is_scraper_result(row)
            if skip:
                if reason == "suggestion":
                    skipped_suggestions += 1
                elif reason == "no_results":
                    skipped_no_results += 1
                continue

            transformed = transform(row)

            if "alternate_words" in transformed:
                alternate_rows += 1

            rows.append(transformed)

            if total_rows % 5000 == 0:
                print(
                    f"Processed {total_rows:,} source rows; "
                    f"kept {len(rows):,}",
                    flush=True,
                )

    print("Alphabetizing...", flush=True)
    rows.sort(key=lambda row: row["word"].casefold())

    print(f"Writing {len(rows):,} entries to {args.output}...", flush=True)
    write_json_array(rows, args.output)

    print(f"Source rows:         {total_rows:,}")
    print(f"Dictionary entries:  {len(rows):,}")
    print(f"Alternate spellings: {alternate_rows:,}")
    print(f"Skipped suggestions: {skipped_suggestions:,}")
    print(f"Skipped no-results:  {skipped_no_results:,}")
    print(f"Wrote:               {args.output}")


if __name__ == "__main__":
    main()
