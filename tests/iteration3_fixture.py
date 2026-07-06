from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

from scripts.contract_common import load_object, sha256

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SYMBOLS_CONFIG = load_object(PROJECT_ROOT / "config/iteration_16_symbols.json")
COLLECTION_CONFIG = load_object(PROJECT_ROOT / "config/iteration_16_collection.json")
TODAY = date(2026, 7, 5)
SNAPSHOT_PATH = "snapshots/2026-07-05T234500Z-test"


def write_data_files(root: Path, snapshot_path: str = SNAPSHOT_PATH) -> Path:
    snapshot = root / snapshot_path
    snapshot.mkdir(parents=True, exist_ok=True)
    csv_path = snapshot / "market_prices.csv"
    rows = []
    for index, symbol in enumerate(sorted(SYMBOLS_CONFIG["required_symbols"]), start=1):
        base = 10.0 + index
        rows.append(
            {
                "canonical_ticker": symbol,
                "session_date": "2026-05-29",
                "adjusted_open": str(base),
                "adjusted_high": str(base + 1.0),
                "adjusted_low": str(base - 1.0),
                "adjusted_close": str(base + 0.5),
                "volume": str(1000 * index),
                "source_symbol": symbol,
                "delisting_return": "",
                "corporate_action_note": "provider_adjustment_factor=1;method=test_fixture",
            }
        )
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLLECTION_CONFIG["required_csv_fields"])
        writer.writeheader()
        writer.writerows(rows)
    per_symbol = {
        symbol: {
            "row_count": 1,
            "start_date": "2026-05-29",
            "end_date": "2026-05-29",
            "provider_metadata": {
                "symbol": symbol,
                "request_url": f"https://fixture.invalid/{symbol}",
                "retrieved_at_utc": "2026-07-05T23:45:00Z",
                "attempt_count": 1,
            },
        }
        for symbol in SYMBOLS_CONFIG["required_symbols"]
    }
    receipt = {
        "receipt_version": "1.0.0",
        "iteration": 16,
        "contract_id": COLLECTION_CONFIG["contract_id"],
        "provider_name": "Fixture Provider",
        "provider_host": "fixture.invalid",
        "collected_at_utc": "2026-07-05T23:45:00Z",
        "requested_start_date": "2026-05-29",
        "requested_end_date": "2026-07-05",
        "actual_start_date": "2026-05-29",
        "actual_end_date": "2026-05-29",
        "actual_end_date_all_symbols": "2026-05-29",
        "target_end_date": "2026-07-24",
        "target_window_complete": False,
        "required_symbols": SYMBOLS_CONFIG["required_symbols"],
        "row_count": len(rows),
        "symbol_count": len(per_symbol),
        "request_count": len(per_symbol),
        "per_symbol": per_symbol,
        "adjustment_method": "adjusted_close/raw_close factor applied identically to open, high, low, and close",
        "corporate_action_adjusted": True,
        "regular_session_only": True,
        "synthetic_prices_used": False,
        "source_data_modified": False,
        "csv_sha256": sha256(csv_path),
        "validated_row_count": len(rows),
    }
    (snapshot / "collection_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return snapshot
