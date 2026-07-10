from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .collector_common import write_jsonl
from .deduplicate_news import deduplicate_records
from .normalize_news import read_jsonl
from .tag_catalysts import tag_catalysts
from .tag_infrastructure_layers import tag_infrastructure_layers


def transform_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    transformed = deduplicate_records(records)
    output: list[dict[str, Any]] = []
    for record in transformed:
        updated = dict(record)
        updated["catalyst_tags"] = tag_catalysts(updated)
        updated["ai_infrastructure_layers"] = tag_infrastructure_layers(updated)
        updated["validation"] = "transformed_valid"
        output.append(updated)
    output.sort(
        key=lambda record: (
            record["published_at_utc"],
            record["ticker"],
            record["event_id"],
            record["record_id"],
        )
    )
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Normalize, deduplicate, and tag public news records")
    parser.add_argument("--input", action="append", type=Path, required=True, help="Input JSONL path; repeat for multiple sources")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    records = read_jsonl(args.input)
    write_jsonl(transform_records(records), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
