from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .collector_common import CollectorError, require
from .company_source_live_compat import HTML_RELEASE_INDEX_MAX_BYTES

EXPECTED_DOCUMENT_LIMITS = {
    "primary_document": 2_000_000,
    "filing_index": 1_500_000,
    "exhibit_document": 1_500_000,
}


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CollectorError(f"cannot read valid JSON: {path}") from exc
    require(isinstance(value, dict), f"expected JSON object: {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise CollectorError(f"cannot read JSONL: {path}") from exc
    records: list[dict[str, Any]] = []
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CollectorError(f"invalid JSONL at {path}:{number}") from exc
        require(isinstance(value, dict), f"expected JSON object at {path}:{number}")
        records.append(value)
    return records


def configured_company_sources(config: dict[str, Any]) -> tuple[list[str], Counter[str]]:
    require(config.get("schema_version") == "1.0.0", "unsupported company source config")
    sources = config.get("sources")
    require(isinstance(sources, list) and sources, "company source config is empty")
    tickers: list[str] = []
    kinds: Counter[str] = Counter()
    for index, source in enumerate(sources):
        require(isinstance(source, dict), f"company sources[{index}] must be an object")
        ticker = str(source.get("ticker", "")).strip().upper()
        kind = str(source.get("source_kind", "feed")).strip().casefold()
        require(ticker and kind in {"feed", "html_release_index"}, f"invalid company source at index {index}")
        require(ticker not in tickers, f"duplicate company source ticker: {ticker}")
        tickers.append(ticker)
        kinds[kind] += 1
    return tickers, kinds


def configured_sec_entities(config: dict[str, Any]) -> list[str]:
    require(config.get("schema_version") == "1.0.0", "unsupported SEC company config")
    companies = config.get("companies")
    require(isinstance(companies, list) and companies, "SEC company config is empty")
    tickers = [str(company.get("ticker", "")).strip().upper() for company in companies if isinstance(company, dict)]
    require(all(tickers) and len(set(tickers)) == len(tickers), "SEC company tickers must be unique and non-empty")
    return tickers


def assess_live_source_coverage(
    *,
    company_config: dict[str, Any],
    sec_config: dict[str, Any],
    company_metrics: dict[str, Any],
    sec_metrics: dict[str, Any],
    company_records: list[dict[str, Any]],
    sec_records: list[dict[str, Any]],
) -> dict[str, Any]:
    company_tickers, company_kinds = configured_company_sources(company_config)
    sec_tickers = configured_sec_entities(sec_config)
    require(set(company_tickers) == set(sec_tickers), "company and SEC configured entities disagree")

    company_counts = Counter(str(record.get("ticker", "")).strip().upper() for record in company_records)
    sec_counts = Counter(str(record.get("ticker", "")).strip().upper() for record in sec_records)
    html_tickers = {
        str(source["ticker"]).strip().upper()
        for source in company_config["sources"]
        if str(source.get("source_kind", "feed")).strip().casefold() == "html_release_index"
    }

    company_failures = company_metrics.get("failures")
    sec_failures = sec_metrics.get("failures")
    enrichment_failures = sec_metrics.get("enrichment_failures", [])
    enrichment_skips = sec_metrics.get("enrichment_skips", [])
    require(isinstance(company_failures, list), "company failures must be a list")
    require(isinstance(sec_failures, list), "SEC failures must be a list")
    require(isinstance(enrichment_failures, list), "SEC enrichment failures must be a list")
    require(isinstance(enrichment_skips, list), "SEC enrichment skips must be a list")

    source_kind_counts = company_metrics.get("source_kind_counts")
    require(isinstance(source_kind_counts, dict), "company source kind metrics are missing")
    observed_kind_counts = {key: int(value) for key, value in source_kind_counts.items()}

    configured_sec_count = int(sec_metrics.get("configured_source_count", -1))
    sec_record_tickers = set(sec_counts)
    sec_entities_accounted_for = (
        configured_sec_count == len(sec_tickers)
        and sec_record_tickers.issubset(set(sec_tickers))
    )

    checks = {
        "company_provider_identity": company_metrics.get("provider") == "official_company_source",
        "company_all_configured_sources_requested": int(company_metrics.get("configured_source_count", -1)) == len(company_tickers),
        "company_source_kinds_match_config": observed_kind_counts == dict(company_kinds),
        "company_provider_failures_empty": company_failures == [],
        "company_html_index_limit_exact": company_metrics.get("html_release_index_max_bytes") == HTML_RELEASE_INDEX_MAX_BYTES,
        "html_release_index_returned_records": all(company_counts[ticker] > 0 for ticker in html_tickers),
        "sec_provider_identity": sec_metrics.get("provider") == "sec_edgar",
        "sec_all_configured_entities_accounted_for": sec_entities_accounted_for,
        "sec_provider_failures_empty": sec_failures == [],
        "sec_enrichment_failures_empty": enrichment_failures == [],
        "sec_document_limits_exact": sec_metrics.get("document_byte_limits") == EXPECTED_DOCUMENT_LIMITS,
        "no_response_too_large_failure": not any("response_too_large" in str(value) for value in enrichment_failures),
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    return {
        "schema_version": "1.0.0",
        "status": "validated" if not failed else "failed",
        "coverage_valid": not failed,
        "checks": checks,
        "failed_checks": failed,
        "configured_entities": sorted(sec_tickers),
        "company_record_counts": {ticker: company_counts[ticker] for ticker in sorted(company_tickers)},
        "sec_record_counts": {ticker: sec_counts[ticker] for ticker in sorted(sec_tickers)},
        "sec_empty_entity_tickers": sorted(ticker for ticker in sec_tickers if sec_counts[ticker] == 0),
        "html_release_index_tickers": sorted(html_tickers),
        "company_request_count": int(company_metrics.get("request_count", 0)),
        "sec_request_count": int(sec_metrics.get("request_count", 0)),
        "sec_enrichment_skip_count": len(enrichment_skips),
        "sec_enrichment_skips": sorted(str(value) for value in enrichment_skips),
        "publication_enabled": False,
        "repository_mutation_enabled": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify live primary-source coverage without publication")
    parser.add_argument("--company-config", type=Path, required=True)
    parser.add_argument("--sec-config", type=Path, required=True)
    parser.add_argument("--company-metrics", type=Path, required=True)
    parser.add_argument("--sec-metrics", type=Path, required=True)
    parser.add_argument("--company-records", type=Path, required=True)
    parser.add_argument("--sec-records", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    report = assess_live_source_coverage(
        company_config=read_json(args.company_config),
        sec_config=read_json(args.sec_config),
        company_metrics=read_json(args.company_metrics),
        sec_metrics=read_json(args.sec_metrics),
        company_records=read_jsonl(args.company_records),
        sec_records=read_jsonl(args.sec_records),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    require(report["coverage_valid"] is True, f"live source coverage failed: {report['failed_checks']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
