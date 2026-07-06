"""Normalize provider chart payloads into the frozen public CSV row format."""
from __future__ import annotations

import math
from datetime import date, datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from scripts.contract_common import require
from scripts.provider_adapter import ProviderResponse


def _positive(value: Any, field: str, symbol: str, session: date) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{symbol} {session}: invalid {field}") from exc
    require(math.isfinite(number) and number > 0.0, f"{symbol} {session}: invalid {field}")
    return number


def _session_from_timestamp(value: Any, timezone_name: str) -> date:
    try:
        timestamp = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("provider returned an invalid session timestamp") from exc
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone(ZoneInfo(timezone_name)).date()


def _event_notes(result: dict[str, Any], timezone_name: str) -> dict[date, list[str]]:
    notes: dict[date, list[str]] = {}
    events = result.get("events")
    if not isinstance(events, dict):
        return notes
    for event_type in ("dividends", "splits"):
        event_map = events.get(event_type)
        if not isinstance(event_map, dict):
            continue
        for event in event_map.values():
            if not isinstance(event, dict) or "date" not in event:
                continue
            session = _session_from_timestamp(event["date"], timezone_name)
            detail = (
                f"dividend={event.get('amount', 'unknown')}"
                if event_type == "dividends"
                else f"split={event.get('splitRatio', 'unknown')}"
            )
            notes.setdefault(session, []).append(detail)
    return notes


def _provider_metadata(meta: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "symbol",
        "currency",
        "exchangeName",
        "fullExchangeName",
        "instrumentType",
        "exchangeTimezoneName",
        "dataGranularity",
        "firstTradeDate",
        "gmtoffset",
    )
    return {field: meta[field] for field in fields if field in meta and meta[field] is not None}


def normalize_chart_payload(
    response: ProviderResponse,
    *,
    canonical_ticker: str,
    start_date: date,
    end_date: date,
    timezone_name: str,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    chart = response.payload.get("chart")
    require(isinstance(chart, dict), f"{canonical_ticker}: chart response missing")
    require(chart.get("error") in (None, {}), f"{canonical_ticker}: provider error: {chart.get('error')}")
    results = chart.get("result")
    require(isinstance(results, list) and len(results) == 1, f"{canonical_ticker}: unexpected result count")
    result = results[0]
    require(isinstance(result, dict), f"{canonical_ticker}: malformed chart result")

    meta = result.get("meta")
    require(isinstance(meta, dict), f"{canonical_ticker}: provider metadata missing")
    provider_symbol = str(meta.get("symbol") or "").strip().upper()
    require(provider_symbol == canonical_ticker, f"{canonical_ticker}: provider returned symbol {provider_symbol or 'EMPTY'}")
    require(str(meta.get("dataGranularity") or "1d") == "1d", f"{canonical_ticker}: provider did not return daily bars")

    timestamps = result.get("timestamp")
    indicators = result.get("indicators")
    require(isinstance(timestamps, list), f"{canonical_ticker}: timestamps missing")
    require(isinstance(indicators, dict), f"{canonical_ticker}: indicators missing")
    quote_sets = indicators.get("quote")
    adjusted_sets = indicators.get("adjclose")
    require(isinstance(quote_sets, list) and len(quote_sets) == 1, f"{canonical_ticker}: quote data missing")
    require(isinstance(adjusted_sets, list) and len(adjusted_sets) == 1, f"{canonical_ticker}: adjusted close missing")
    quote = quote_sets[0]
    adjusted = adjusted_sets[0]
    require(isinstance(quote, dict) and isinstance(adjusted, dict), f"{canonical_ticker}: malformed indicators")

    opens = quote.get("open")
    highs = quote.get("high")
    lows = quote.get("low")
    closes = quote.get("close")
    volumes = quote.get("volume")
    adjusted_closes = adjusted.get("adjclose")
    arrays = (opens, highs, lows, closes, volumes, adjusted_closes)
    require(all(isinstance(values, list) for values in arrays), f"{canonical_ticker}: indicator arrays missing")
    require(all(len(values) == len(timestamps) for values in arrays), f"{canonical_ticker}: indicator lengths differ")

    actions = _event_notes(result, timezone_name)
    rows: list[dict[str, str]] = []
    seen: set[date] = set()
    for index, timestamp in enumerate(timestamps):
        session = _session_from_timestamp(timestamp, timezone_name)
        if session < start_date or session > end_date:
            continue
        require(session.weekday() < 5, f"{canonical_ticker}: weekend session {session}")
        require(session not in seen, f"{canonical_ticker}: duplicate session {session}")
        seen.add(session)

        values = (opens[index], highs[index], lows[index], closes[index], adjusted_closes[index])
        require(not any(value is None for value in values), f"{canonical_ticker} {session}: incomplete OHLC data")
        raw_open = _positive(opens[index], "open", canonical_ticker, session)
        raw_high = _positive(highs[index], "high", canonical_ticker, session)
        raw_low = _positive(lows[index], "low", canonical_ticker, session)
        raw_close = _positive(closes[index], "close", canonical_ticker, session)
        adjusted_close = _positive(adjusted_closes[index], "adjusted_close", canonical_ticker, session)
        require(raw_high >= max(raw_open, raw_close, raw_low), f"{canonical_ticker} {session}: raw high invariant failed")
        require(raw_low <= min(raw_open, raw_close, raw_high), f"{canonical_ticker} {session}: raw low invariant failed")

        factor = adjusted_close / raw_close
        require(math.isfinite(factor) and factor > 0.0, f"{canonical_ticker} {session}: invalid adjustment factor")
        adjusted_open = raw_open * factor
        adjusted_high = raw_high * factor
        adjusted_low = raw_low * factor
        adjusted_close_recomputed = raw_close * factor
        require(adjusted_high >= max(adjusted_open, adjusted_close_recomputed, adjusted_low), f"{canonical_ticker} {session}: adjusted high invariant failed")
        require(adjusted_low <= min(adjusted_open, adjusted_close_recomputed, adjusted_high), f"{canonical_ticker} {session}: adjusted low invariant failed")

        volume = ""
        if volumes[index] is not None:
            try:
                volume_number = float(volumes[index])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{canonical_ticker} {session}: invalid volume") from exc
            require(math.isfinite(volume_number) and volume_number >= 0.0, f"{canonical_ticker} {session}: invalid volume")
            require(volume_number.is_integer(), f"{canonical_ticker} {session}: fractional volume")
            volume = str(int(volume_number))

        note_parts = [
            "provider_adjustment_factor=" + format(factor, ".15g"),
            "method=adjusted_close_divided_by_raw_close_applied_to_all_ohlc",
        ]
        if session in actions:
            note_parts.append("events=" + "|".join(sorted(actions[session])))
        rows.append(
            {
                "canonical_ticker": canonical_ticker,
                "session_date": session.isoformat(),
                "adjusted_open": format(adjusted_open, ".15g"),
                "adjusted_high": format(adjusted_high, ".15g"),
                "adjusted_low": format(adjusted_low, ".15g"),
                "adjusted_close": format(adjusted_close_recomputed, ".15g"),
                "volume": volume,
                "source_symbol": provider_symbol,
                "delisting_return": "",
                "corporate_action_note": ";".join(note_parts),
            }
        )

    require(rows, f"{canonical_ticker}: no usable sessions returned")
    rows.sort(key=lambda row: row["session_date"])
    metadata = _provider_metadata(meta)
    metadata.update(
        {
            "request_url": response.request_url,
            "retrieved_at_utc": response.retrieved_at_utc,
            "attempt_count": response.attempt_count,
        }
    )
    return rows, metadata
