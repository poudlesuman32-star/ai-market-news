"""Validate a CSV against the frozen Iteration 16 public market contract."""
from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from scripts.contract_common import CsvSummary, parse_date, parse_positive, require


def validate_market_csv(
    csv_path: Path,
    *,
    symbols_config: dict[str, Any],
    collection_config: dict[str, Any],
    today: date | None = None,
) -> CsvSummary:
    required_symbols = tuple(str(item) for item in symbols_config["required_symbols"])
    required_symbol_set = set(required_symbols)
    expected_fields = list(collection_config["required_csv_fields"])
    collection_start = date.fromisoformat(collection_config["collection_start_date"])
    contract_start = date.fromisoformat(collection_config["contract_start_on_or_before"])
    target_end = date.fromisoformat(collection_config["target_end_date"])
    if today is None:
        today = datetime.now(ZoneInfo(collection_config["timezone"])).date()
    latest_allowed = min(today, target_end)

    rows = 0
    symbols: set[str] = set()
    sessions: list[date] = []
    seen: set[tuple[str, date]] = set()
    observed_order: list[tuple[str, date]] = []

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        require(reader.fieldnames is not None, "market CSV has no header")
        require(reader.fieldnames == expected_fields, "market CSV fields or field order do not match the contract")
        for line_number, row in enumerate(reader, start=2):
            ticker = str(row["canonical_ticker"]).strip().upper()
            require(ticker in required_symbol_set, f"unknown symbol at line {line_number}: {ticker}")
            source_symbol = str(row["source_symbol"]).strip().upper()
            require(source_symbol == ticker, f"cross-ticker substitution at line {line_number}")
            require(not (ticker == "SNDK" and source_symbol == "WDC"), "WDC may not be substituted for SNDK")

            session = parse_date(row["session_date"], "session_date", line_number)
            require(session.weekday() < 5, f"weekend session at line {line_number}")
            require(session >= collection_start, f"session precedes collection start at line {line_number}")
            require(session <= latest_allowed, f"future session at line {line_number}")
            key = (ticker, session)
            require(key not in seen, f"duplicate ticker-session row: {ticker} {session}")
            seen.add(key)
            observed_order.append(key)

            adjusted_open = parse_positive(row["adjusted_open"], "adjusted_open", line_number)
            adjusted_high = parse_positive(row["adjusted_high"], "adjusted_high", line_number)
            adjusted_low = parse_positive(row["adjusted_low"], "adjusted_low", line_number)
            adjusted_close = parse_positive(row["adjusted_close"], "adjusted_close", line_number)
            require(
                adjusted_high >= max(adjusted_open, adjusted_close, adjusted_low),
                f"adjusted_high invariant failed at line {line_number}",
            )
            require(
                adjusted_low <= min(adjusted_open, adjusted_close, adjusted_high),
                f"adjusted_low invariant failed at line {line_number}",
            )

            volume_text = str(row["volume"]).strip()
            if volume_text:
                require(volume_text.isdigit(), f"invalid volume at line {line_number}")
            require(str(row["delisting_return"]).strip() == "", "delisting-return ingestion is not implemented")

            rows += 1
            symbols.add(ticker)
            sessions.append(session)

    require(rows > 0, "market CSV is empty")
    require(symbols == required_symbol_set, "market CSV does not contain every required symbol")
    require(observed_order == sorted(observed_order), "market CSV is not sorted by canonical_ticker and session_date")
    require(min(sessions) <= contract_start, "market CSV begins after the contract start requirement")

    return CsvSummary(
        row_count=rows,
        symbol_count=len(symbols),
        symbols=tuple(sorted(symbols)),
        start_date=min(sessions).isoformat(),
        end_date=max(sessions).isoformat(),
    )
