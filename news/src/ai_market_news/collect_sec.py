from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .collector_common import CollectorError, build_public_record, load_json_object, require, write_jsonl


def collect_sec_fixture(payload: dict[str, Any], *, collected_at_utc: str) -> list[dict[str, Any]]:
    filings = payload.get("filings")
    require(isinstance(filings, list), "SEC fixture must contain a filings list")

    records: list[dict[str, Any]] = []
    seen_accessions: set[str] = set()
    for index, filing in enumerate(filings):
        require(isinstance(filing, dict), f"filings[{index}] must be an object")
        accession = str(filing.get("accession_number", "")).strip()
        require(bool(accession), f"filings[{index}].accession_number is required")
        require(accession not in seen_accessions, f"duplicate SEC accession number: {accession}")
        seen_accessions.add(accession)

        form = str(filing.get("form", "")).strip().upper()
        require(bool(form), f"filings[{index}].form is required")
        company_name = str(filing.get("company_name", "")).strip()
        require(bool(company_name), f"filings[{index}].company_name is required")

        records.append(
            build_public_record(
                ticker=str(filing.get("ticker", "")),
                published_at_utc=str(filing.get("filed_at_utc", "")),
                collected_at_utc=collected_at_utc,
                source_type="sec_filing",
                source_name=f"{company_name} SEC filing",
                source_url=str(filing.get("primary_document_url", "")),
                headline=str(filing.get("headline", "")),
                summary=str(filing.get("summary", "")),
                provider="sec_edgar",
                provider_article_id=accession,
                source_ticker=str(filing.get("ticker", "")),
                filing_type=form,
                event_identity=accession,
                primary_source=True,
            )
        )

    records.sort(key=lambda row: (row["published_at_utc"], row["ticker"], row["provider_article_id"]))
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect public SEC filing news from a controlled fixture")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--collected-at", required=True)
    parser.add_argument("--mode", choices=["fixture", "live"], default="fixture")
    args = parser.parse_args(argv)

    if args.mode != "fixture":
        raise CollectorError("live SEC collection is not authorized in this gate")

    records = collect_sec_fixture(load_json_object(args.input), collected_at_utc=args.collected_at)
    write_jsonl(records, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
