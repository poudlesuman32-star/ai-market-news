from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .collector_common import CollectorError, build_public_record, load_json_object, require, write_jsonl


def collect_company_release_fixture(payload: dict[str, Any], *, collected_at_utc: str) -> list[dict[str, Any]]:
    releases = payload.get("releases")
    require(isinstance(releases, list), "company fixture must contain a releases list")

    records: list[dict[str, Any]] = []
    seen_release_ids: set[str] = set()
    for index, release in enumerate(releases):
        require(isinstance(release, dict), f"releases[{index}] must be an object")
        release_id = str(release.get("release_id", "")).strip()
        require(bool(release_id), f"releases[{index}].release_id is required")
        require(release_id not in seen_release_ids, f"duplicate company release ID: {release_id}")
        seen_release_ids.add(release_id)

        source_name = str(release.get("source_name", "")).strip()
        require(bool(source_name), f"releases[{index}].source_name is required")

        records.append(
            build_public_record(
                ticker=str(release.get("ticker", "")),
                published_at_utc=str(release.get("published_at_utc", "")),
                collected_at_utc=collected_at_utc,
                source_type="company_release",
                source_name=source_name,
                source_url=str(release.get("source_url", "")),
                headline=str(release.get("headline", "")),
                summary=str(release.get("summary", "")),
                provider="official_company_source",
                provider_article_id=release_id,
                source_ticker=str(release.get("ticker", "")),
                filing_type=None,
                event_identity=release_id,
                primary_source=True,
            )
        )

    records.sort(key=lambda row: (row["published_at_utc"], row["ticker"], row["provider_article_id"]))
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect official company news from a controlled fixture")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--collected-at", required=True)
    parser.add_argument("--mode", choices=["fixture", "live"], default="fixture")
    args = parser.parse_args(argv)

    if args.mode != "fixture":
        raise CollectorError("live company-source collection is not authorized in this gate")

    records = collect_company_release_fixture(load_json_object(args.input), collected_at_utc=args.collected_at)
    write_jsonl(records, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
