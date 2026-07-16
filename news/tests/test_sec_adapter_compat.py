from __future__ import annotations

import unittest

from ai_market_news.sec_adapter_compat import normalize_same_accession_index_links


class SecAdapterCompatTests(unittest.TestCase):
    def test_normalizes_root_relative_same_accession_link(self) -> None:
        index_url = (
            "https://www.sec.gov/Archives/edgar/data/723125/000072312526000013/"
            "0000723125-26-000013-index.html"
        )
        body = b"""<table><tr><td><a href='/Archives/edgar/data/723125/000072312526000013/a2026q3ex991-pressrelease.htm'>Exhibit</a></td><td>EX-99.1</td></tr></table>"""
        normalized = normalize_same_accession_index_links(body, index_url=index_url).decode("utf-8")
        self.assertIn("href='a2026q3ex991-pressrelease.htm'", normalized)

    def test_preserves_cross_accession_link_for_fail_closed_parser(self) -> None:
        index_url = (
            "https://www.sec.gov/Archives/edgar/data/723125/000072312526000013/"
            "0000723125-26-000013-index.html"
        )
        unsafe = "/Archives/edgar/data/723125/000072312526999999/a2026q3ex991-pressrelease.htm"
        body = f"<table><tr><td><a href='{unsafe}'>Exhibit</a></td><td>EX-99.1</td></tr></table>".encode()
        normalized = normalize_same_accession_index_links(body, index_url=index_url).decode("utf-8")
        self.assertIn(unsafe, normalized)

    def test_preserves_absolute_url_for_fail_closed_parser(self) -> None:
        index_url = (
            "https://www.sec.gov/Archives/edgar/data/723125/000072312526000013/"
            "0000723125-26-000013-index.html"
        )
        unsafe = "https://example.com/exhibit.htm"
        body = f"<table><tr><td><a href='{unsafe}'>Exhibit</a></td><td>EX-99.1</td></tr></table>".encode()
        normalized = normalize_same_accession_index_links(body, index_url=index_url).decode("utf-8")
        self.assertIn(unsafe, normalized)


if __name__ == "__main__":
    unittest.main()
