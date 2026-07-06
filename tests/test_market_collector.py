import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from scripts.collect_market_window import collect_market_window, resolve_collection_window, write_collection_outputs
from scripts.contract_common import ContractError, load_object
from scripts.market_normalizer import normalize_chart_payload
from scripts.provider_adapter import ProviderResponse

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/provider/yahoo_chart_nvda.json"
SYMBOLS = load_object(ROOT / "config/iteration_16_symbols.json")
COLLECTION = load_object(ROOT / "config/iteration_16_collection.json")
START = date(2026, 5, 29)
AS_OF = date(2026, 7, 5)


def payload_for(symbol, broken=False):
    value = json.loads(FIXTURE.read_text())
    result = value["chart"]["result"][0]
    result["meta"]["symbol"] = symbol
    result["timestamp"] = result["timestamp"][:1]
    quote = result["indicators"]["quote"][0]
    adjusted = result["indicators"]["adjclose"][0]
    for field in ("open", "high", "low", "close", "volume"):
        quote[field] = quote[field][:1]
    adjusted["adjclose"] = adjusted["adjclose"][:1]
    if broken:
        quote["open"][0] = None
    return value


class FakeAdapter:
    provider_name = "Fixture Provider"
    provider_host = "fixture.invalid"

    def __init__(self, wrong=None, fail=None, broken=None):
        self.wrong = wrong
        self.fail = fail
        self.broken = broken
        self.request_count = 0

    def fetch(self, symbol, start_date, end_date):
        self.request_count += 1
        if symbol == self.fail:
            raise ValueError("required symbol failed")
        returned = "WDC" if symbol == self.wrong else symbol
        return ProviderResponse(payload_for(returned, symbol == self.broken), "fixture", "2026-07-05T23:45:00Z", 1)


class MarketCollectorTests(unittest.TestCase):
    def test_window_is_capped_at_target(self):
        self.assertEqual(resolve_collection_window(COLLECTION, as_of_date=date(2026, 8, 1))[1], date(2026, 7, 24))

    def test_adjustment_factor_is_applied_to_every_ohlc_field(self):
        response = ProviderResponse(json.loads(FIXTURE.read_text()), "fixture", "2026-07-05T23:45:00Z", 1)
        rows, metadata = normalize_chart_payload(
            response,
            canonical_ticker="NVDA",
            start_date=START,
            end_date=date(2026, 6, 1),
            timezone_name="America/New_York",
        )
        self.assertEqual(
            [rows[0][name] for name in ("adjusted_open", "adjusted_high", "adjusted_low", "adjusted_close")],
            ["50", "55", "45", "50"],
        )
        self.assertEqual(metadata["symbol"], "NVDA")

    def test_collects_all_symbols_and_writes_validated_outputs(self):
        rows, receipt = collect_market_window(
            symbols_config=SYMBOLS,
            collection_config=COLLECTION,
            adapter=FakeAdapter(),
            start_date=START,
            end_date=AS_OF,
            as_of_date=AS_OF,
            collected_at_utc=datetime(2026, 7, 5, 23, 45, tzinfo=timezone.utc),
        )
        self.assertEqual((len(rows), receipt["symbol_count"], receipt["request_count"]), (11, 11, 11))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            final = write_collection_outputs(
                rows=rows,
                receipt=receipt,
                output_path=root / "market_prices.csv",
                receipt_path=root / "collection_receipt.json",
                symbols_config=SYMBOLS,
                collection_config=COLLECTION,
                as_of_date=AS_OF,
            )
            self.assertEqual(final["validated_row_count"], 11)
            self.assertEqual(len(final["csv_sha256"]), 64)

    def test_invalid_required_ticker_aborts_without_synthetic_fallback(self):
        with self.assertRaisesRegex(ContractError, "provider returned symbol"):
            collect_market_window(
                symbols_config=SYMBOLS,
                collection_config=COLLECTION,
                adapter=FakeAdapter(wrong="SNDK"),
                start_date=START,
                end_date=AS_OF,
                as_of_date=AS_OF,
            )
        with self.assertRaisesRegex(ValueError, "required symbol failed"):
            collect_market_window(
                symbols_config=SYMBOLS,
                collection_config=COLLECTION,
                adapter=FakeAdapter(fail="MU"),
                start_date=START,
                end_date=AS_OF,
                as_of_date=AS_OF,
            )
        with self.assertRaisesRegex(ContractError, "incomplete OHLC"):
            collect_market_window(
                symbols_config=SYMBOLS,
                collection_config=COLLECTION,
                adapter=FakeAdapter(broken="CAR"),
                start_date=START,
                end_date=AS_OF,
                as_of_date=AS_OF,
            )


if __name__ == "__main__":
    unittest.main()
