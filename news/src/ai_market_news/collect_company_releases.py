from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .collector_common import build_public_record, load_json_object, require, write_jsonl
from .company_feed_adapter import collect_company_feeds_live


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


def write_metrics(path: Path | None, value: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect official company release metadata")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--metrics-output", type=Path)
    parser.add_argument("--collected-at", required=True)
    parser.add_argument("--mode", choices=["fixture", "live"], default="fixture")
    parser.add_argument("--user-agent", default="")
    parser.add_argument("--lookback-days", type=int, default=7)
    args = parser.parse_args(argv)

    if args.mode == "fixture":
        require(args.input is not None, "fixture company collection requires --input")
        records = collect_company_release_fixture(load_json_object(args.input), collected_at_utc=args.collected_at)
        metrics = {
            "schema_version": "1.0.0",
            "provider": "official_company_source",
            "request_count": 0,
            "configured_source_count": 0,
            "record_count": len(records),
            "failures": [],
            "article_pages_fetched": False,
        }
    else:
        require(args.config is not None, "live company collection requires --config")
        records, metrics = collect_company_feeds_live(
            load_json_object(args.config),
            collected_at_utc=args.collected_at,
            user_agent=args.user_agent,
            lookback_days=args.lookback_days,
        )

    write_jsonl(records, args.output)
    write_metrics(args.metrics_output, metrics)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
