from __future__ import annotations

import unittest
from unittest.mock import patch

from ai_market_news import sec_adapter
from ai_market_news.live_http import HttpResult
from ai_market_news.sec_adapter_compat import (
    EXHIBIT_DOCUMENT_MAX_BYTES,
    FILING_INDEX_MAX_BYTES,
    PRIMARY_DOCUMENT_MAX_BYTES,
    _reclassify_enrichment_metrics,
    collect_sec_live,
    parse_substantive_exhibit_documents,
)


class SecEnrichmentPolicyTests(unittest.TestCase):
    def test_selects_safe_substantive_exhibits_and_excludes_xbrl(self) -> None:
        body = b"""
        <table>
          <tr><td><a href='underwriting.htm'>Underwriting agreement</a></td><td>EX-1.1</td></tr>
          <tr><td><a href='legal-opinion.htm'>Legal opinion</a></td><td>EX-5.1</td></tr>
          <tr><td><a href='schema.xsd'>XBRL schema</a></td><td>EX-101.SCH</td></tr>
        </table>
        """
        selected = parse_substantive_exhibit_documents(body, "text/html")
        self.assertEqual(selected, [("EX-1.1", "underwriting.htm"), ("EX-5.1", "legal-opinion.htm")])

    def test_reclassifies_absent_substantive_exhibit_as_skip(self) -> None:
        result = _reclassify_enrichment_metrics(
            {
                "enrichment_failures": [
                    "sec_edgar:NVDA:0001045810-26-000056:filing_index:exhibit_not_found",
                    "sec_edgar:MU:0000723125-26-000015:primary_document:response_too_large",
                ]
            }
        )
        self.assertEqual(
            result["enrichment_failures"],
            ["sec_edgar:MU:0000723125-26-000015:primary_document:response_too_large"],
        )
        self.assertEqual(
            result["enrichment_skips"],
            ["sec_edgar:NVDA:0001045810-26-000056:filing_index:no_substantive_exhibit_present"],
        )

    def test_applies_stage_specific_bounded_response_limits(self) -> None:
        observed_limits: list[int] = []
        index_url = (
            "https://www.sec.gov/Archives/edgar/data/1045810/000119312526275783/"
            "0001193125-26-275783-index.html"
        )
        primary_url = "https://www.sec.gov/Archives/edgar/data/1045810/000119312526275783/d48176d8k.htm"
        exhibit_url = "https://www.sec.gov/Archives/edgar/data/1045810/000119312526275783/underwriting.htm"

        def document_fetcher(url: str, **kwargs: object) -> HttpResult:
            observed_limits.append(int(kwargs["max_bytes"]))
            if url == index_url:
                body = b"<table><tr><td><a href='underwriting.htm'>Agreement</a></td><td>EX-1.1</td></tr></table>"
            else:
                body = b"readable document"
            return HttpResult(body=body, final_url=url, request_count=1, content_type="text/html")

        def fake_collect(
            _config: dict[str, object],
            *,
            collected_at_utc: str,
            user_agent: str,
            lookback_days: int,
            fetcher: object,
            document_fetcher: object,
        ) -> tuple[list[dict[str, object]], dict[str, object]]:
            del collected_at_utc, user_agent, lookback_days, fetcher
            fetch_document = document_fetcher
            fetch_document(primary_url, max_bytes=1, allowed_hosts={"sec.gov"}, user_agent="test", accept="text/html", rate_limiter=object())
            index = fetch_document(index_url, max_bytes=1, allowed_hosts={"sec.gov"}, user_agent="test", accept="text/html", rate_limiter=object())
            selected = sec_adapter.parse_exhibit_documents(index.body, index.content_type)
            self.assertEqual(selected, [("EX-1.1", "underwriting.htm")])
            fetch_document(exhibit_url, max_bytes=1, allowed_hosts={"sec.gov"}, user_agent="test", accept="text/html", rate_limiter=object())
            return [], {"enrichment_failures": []}

        with patch.object(sec_adapter, "collect_sec_live", fake_collect):
            _, metrics = collect_sec_live(
                {},
                collected_at_utc="2026-07-18T00:00:00Z",
                user_agent="PPI test test@example.com",
                lookback_days=30,
                document_fetcher=document_fetcher,
            )
        self.assertEqual(
            observed_limits,
            [PRIMARY_DOCUMENT_MAX_BYTES, FILING_INDEX_MAX_BYTES, EXHIBIT_DOCUMENT_MAX_BYTES],
        )
        self.assertEqual(
            metrics["document_byte_limits"],
            {
                "primary_document": PRIMARY_DOCUMENT_MAX_BYTES,
                "filing_index": FILING_INDEX_MAX_BYTES,
                "exhibit_document": EXHIBIT_DOCUMENT_MAX_BYTES,
            },
        )


if __name__ == "__main__":
    unittest.main()
