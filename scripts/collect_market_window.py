#!/usr/bin/env python3
"""Collect validated corporate-action-adjusted daily bars for Iteration 16."""
from __future__ import annotations

import argparse
import csv
import json
import os
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from scripts.contract_common import load_object, require, sha256
from scripts.market_normalizer import normalize_chart_payload
from scripts.provider_adapter import YahooChartAdapter
from scripts.validate_market_csv import validate_market_csv

ADJUSTMENT_METHOD = "adjusted_close/raw_close factor applied identically to open, high, low, and close"


def resolve_collection_window(collection_config: dict[str, Any], *, as_of_date: date | None = None) -> tuple[date, date]:
    if as_of_date is None:
        as_of_date = datetime.now(ZoneInfo(str(collection_config["timezone"]))).date()
    start_date = date.fromisoformat(collection_config["collection_start_date"])
    target_end = date.fromisoformat(collection_config["target_end_date"])
    require(as_of_date >= start_date, "collection window has not started")
    return start_date, min(as_of_date, target_end)


def collect_market_window(
    *,
    symbols_config: dict[str, Any],
    collection_config: dict[str, Any],
    adapter: Any,
    start_date: date,
    end_date: date,
    as_of_date: date,
    collected_at_utc: datetime | None = None,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    require(symbols_config["contract_id"] == collection_config["contract_id"], "configuration contract ids differ")
    configured_start = date.fromisoformat(collection_config["collection_start_date"])
    target_end = date.fromisoformat(collection_config["target_end_date"])
    require(start_date == configured_start, "collector must request the full frozen start date")
    require(start_date <= end_date, "collection end date precedes start date")
    require(end_date <= target_end, "collection end date exceeds target end date")
    require(end_date <= as_of_date, "future market data collection is prohibited")
    require(collection_config["regular_session_only"] is True, "regular-session-only contract required")
    require(collection_config["corporate_action_adjusted"] is True, "adjusted-data contract required")
    require(collection_config["synthetic_prices_allowed"] is False, "synthetic prices must remain prohibited")

    required_symbols = [str(symbol).upper() for symbol in symbols_config["required_symbols"]]
    require(len(required_symbols) == len(set(required_symbols)), "required symbol list contains duplicates")
    all_rows: list[dict[str, str]] = []
    per_symbol: dict[str, Any] = {}
    for symbol in required_symbols:
        response = adapter.fetch(symbol, start_date, end_date)
        rows, metadata = normalize_chart_payload(
            response,
            canonical_ticker=symbol,
            start_date=start_date,
            end_date=end_date,
            timezone_name=collection_config["timezone"],
        )
        all_rows.extend(rows)
        per_symbol[symbol] = {
            "row_count": len(rows),
            "start_date": rows[0]["session_date"],
            "end_date": rows[-1]["session_date"],
            "provider_metadata": metadata,
        }

    require(set(per_symbol) == set(required_symbols), "not every required symbol was collected")
    all_rows.sort(key=lambda row: (row["canonical_ticker"], row["session_date"]))
    keys = [(row["canonical_ticker"], row["session_date"]) for row in all_rows]
    require(len(keys) == len(set(keys)), "collector produced duplicate ticker-session rows")
    target_complete = all(item["end_date"] >= target_end.isoformat() for item in per_symbol.values())
    collected_at_utc = collected_at_utc or datetime.now(timezone.utc)
    receipt = {
        "receipt_version": "1.0.0",
        "iteration": 16,
        "contract_id": collection_config["contract_id"],
        "provider_name": str(getattr(adapter, "provider_name", "unknown")),
        "provider_host": str(getattr(adapter, "provider_host", "unknown")),
        "collected_at_utc": collected_at_utc.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "requested_start_date": start_date.isoformat(),
        "requested_end_date": end_date.isoformat(),
        "actual_start_date": min(row["session_date"] for row in all_rows),
        "actual_end_date": max(row["session_date"] for row in all_rows),
        "actual_end_date_all_symbols": min(item["end_date"] for item in per_symbol.values()),
        "target_end_date": target_end.isoformat(),
        "target_window_complete": target_complete,
        "required_symbols": required_symbols,
        "row_count": len(all_rows),
        "symbol_count": len(per_symbol),
        "request_count": int(getattr(adapter, "request_count", len(required_symbols))),
        "per_symbol": per_symbol,
        "adjustment_method": ADJUSTMENT_METHOD,
        "corporate_action_adjusted": True,
        "regular_session_only": True,
        "synthetic_prices_used": False,
        "source_data_modified": False,
    }
    return all_rows, receipt


def write_collection_outputs(
    *,
    rows: list[dict[str, str]],
    receipt: dict[str, Any],
    output_path: Path,
    receipt_path: Path,
    symbols_config: dict[str, Any],
    collection_config: dict[str, Any],
    as_of_date: date,
) -> dict[str, Any]:
    require(output_path.resolve() != receipt_path.resolve(), "CSV and receipt paths must differ")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    csv_temp: Path | None = None
    receipt_temp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=output_path.parent, prefix=".market-", suffix=".csv") as handle:
            csv_temp = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=collection_config["required_csv_fields"])
            writer.writeheader()
            writer.writerows(rows)
        summary = validate_market_csv(
            csv_temp,
            symbols_config=symbols_config,
            collection_config=collection_config,
            today=as_of_date,
        )
        final_receipt = dict(receipt)
        final_receipt["csv_sha256"] = sha256(csv_temp)
        final_receipt["validated_row_count"] = summary.row_count
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=receipt_path.parent, prefix=".receipt-", suffix=".json") as handle:
            receipt_temp = Path(handle.name)
            json.dump(final_receipt, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(csv_temp, output_path)
        csv_temp = None
        os.replace(receipt_temp, receipt_path)
        receipt_temp = None
        return final_receipt
    finally:
        if csv_temp is not None:
            csv_temp.unlink(missing_ok=True)
        if receipt_temp is not None:
            receipt_temp.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols-config", type=Path, default=Path("config/iteration_16_symbols.json"))
    parser.add_argument("--collection-config", type=Path, default=Path("config/iteration_16_collection.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt-output", type=Path, required=True)
    args = parser.parse_args()
    try:
        symbols_config = load_object(args.symbols_config)
        collection_config = load_object(args.collection_config)
        start_date, end_date = resolve_collection_window(collection_config)
        as_of_date = datetime.now(ZoneInfo(collection_config["timezone"])).date()
        rows, receipt = collect_market_window(
            symbols_config=symbols_config,
            collection_config=collection_config,
            adapter=YahooChartAdapter(),
            start_date=start_date,
            end_date=end_date,
            as_of_date=as_of_date,
        )
        final_receipt = write_collection_outputs(
            rows=rows,
            receipt=receipt,
            output_path=args.output,
            receipt_path=args.receipt_output,
            symbols_config=symbols_config,
            collection_config=collection_config,
            as_of_date=as_of_date,
        )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"market collection failed: {exc}") from exc
    print(json.dumps(final_receipt, sort_keys=True))


if __name__ == "__main__":
    main()
