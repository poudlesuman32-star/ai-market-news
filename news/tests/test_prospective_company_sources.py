from __future__ import annotations

import json
import unittest
from pathlib import Path

from ai_market_news.collector_common import CollectorError
from ai_market_news.company_source_live_compat import collect_company_feeds_live
from ai_market_news.live_http import HttpResult


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "news/config/official_company_sources.json"
COLLECTED_AT = "2026-07-20T18:00:00Z"


def rss_item(*, title: str, link: str, guid: str, published: str) -> str:
    return (
        "<item>"
        f"<title>{title}</title>"
        f"<link>{link}</link>"
        f"<guid>{guid}</guid>"
        f"<pubDate>{published}</pubDate>"
        f"<description>{title} official summary.</description>"
        "</item>"
    )


def rss(*items: str) -> bytes:
    return ("<rss><channel>" + "".join(items) + "</channel></rss>").encode("utf-8")


class ProspectiveCompanySourceTests(unittest.TestCase):
    def test_multiple_same_ticker_feeds_apply_source_activation(self) -> None:
        newsroom_url = "https://nvidianews.nvidia.com/rss.xml"
        blog_url = "https://feeds.feedburner.com/nvidiablog"
        payloads = {
            newsroom_url: rss(
                rss_item(
                    title="Existing newsroom item",
                    link="https://nvidianews.nvidia.com/news/existing",
                    guid="newsroom-existing",
                    published="Mon, 20 Jul 2026 17:40:00 GMT",
                )
            ),
            blog_url: rss(
                rss_item(
                    title="Pre-activation blog item",
                    link="https://blogs.nvidia.com/blog/pre-activation/",
                    guid="blog-pre",
                    published="Mon, 20 Jul 2026 17:49:00 GMT",
                ),
                rss_item(
                    title="Post-activation blog item",
                    link="https://blogs.nvidia.com/blog/post-activation/",
                    guid="blog-post",
                    published="Mon, 20 Jul 2026 17:51:00 GMT",
                ),
            ),
        }

        def fetcher(url: str, **kwargs: object) -> HttpResult:
            self.assertIn(url, payloads)
            return HttpResult(body=payloads[url], final_url=url, request_count=1, content_type="application/rss+xml")

        config = {
            "schema_version": "1.0.0",
            "sources": [
                {
                    "ticker": "NVDA",
                    "source_name": "NVIDIA Newsroom",
                    "source_kind": "feed",
                    "feed_url": newsroom_url,
                    "allowed_hosts": ["nvidia.com"],
                },
                {
                    "ticker": "NVDA",
                    "source_name": "NVIDIA Blog",
                    "source_kind": "feed",
                    "feed_url": blog_url,
                    "allowed_hosts": ["feedburner.com", "nvidia.com"],
                    "activation_at_utc": "2026-07-20T17:50:00Z",
                },
            ],
        }
        records, metrics = collect_company_feeds_live(
            config,
            collected_at_utc=COLLECTED_AT,
            user_agent="PPI Research contact@example.com",
            lookback_days=7,
            fetcher=fetcher,
        )
        self.assertEqual([record["provider_article_id"] for record in records], ["newsroom-existing", "blog-post"])
        self.assertEqual(metrics["configured_source_count"], 2)
        self.assertEqual(metrics["source_kind_counts"], {"feed": 2, "html_release_index": 0})
        self.assertEqual(metrics["activation_filtered_record_count"], 1)
        self.assertEqual(metrics["overlap_deduplicated_record_count"], 0)
        self.assertEqual(metrics["failures"], [])

    def test_overlapping_feed_link_is_counted_once(self) -> None:
        shared_link = "https://blogs.nvidia.com/blog/shared/"
        urls = ["https://nvidianews.nvidia.com/rss.xml", "https://feeds.feedburner.com/nvidiablog"]
        payloads = {
            urls[0]: rss(
                rss_item(
                    title="Shared item",
                    link=shared_link,
                    guid="newsroom-guid",
                    published="Mon, 20 Jul 2026 17:55:00 GMT",
                )
            ),
            urls[1]: rss(
                rss_item(
                    title="Shared item",
                    link=shared_link,
                    guid="blog-guid",
                    published="Mon, 20 Jul 2026 17:55:00 GMT",
                )
            ),
        }

        def fetcher(url: str, **kwargs: object) -> HttpResult:
            return HttpResult(body=payloads[url], final_url=url, request_count=1, content_type="application/rss+xml")

        config = {
            "schema_version": "1.0.0",
            "sources": [
                {
                    "ticker": "NVDA",
                    "source_name": "NVIDIA Newsroom",
                    "source_kind": "feed",
                    "feed_url": urls[0],
                    "allowed_hosts": ["nvidia.com"],
                },
                {
                    "ticker": "NVDA",
                    "source_name": "NVIDIA Blog",
                    "source_kind": "feed",
                    "feed_url": urls[1],
                    "allowed_hosts": ["feedburner.com", "nvidia.com"],
                },
            ],
        }
        records, metrics = collect_company_feeds_live(
            config,
            collected_at_utc=COLLECTED_AT,
            user_agent="PPI Research contact@example.com",
            lookback_days=7,
            fetcher=fetcher,
        )
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["source_url"], shared_link)
        self.assertEqual(metrics["overlap_deduplicated_record_count"], 1)

    def test_invalid_activation_fails_closed(self) -> None:
        config = {
            "schema_version": "1.0.0",
            "sources": [
                {
                    "ticker": "NVDA",
                    "source_name": "NVIDIA Blog",
                    "source_kind": "feed",
                    "feed_url": "https://feeds.feedburner.com/nvidiablog",
                    "allowed_hosts": ["feedburner.com", "nvidia.com"],
                    "activation_at_utc": "not-a-timestamp",
                }
            ],
        }
        with self.assertRaisesRegex(CollectorError, "activation_at_utc is invalid"):
            collect_company_feeds_live(
                config,
                collected_at_utc=COLLECTED_AT,
                user_agent="PPI Research contact@example.com",
                lookback_days=7,
            )

    def test_reviewed_config_adds_only_prospective_nvidia_blog(self) -> None:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        blog = [source for source in config["sources"] if source["source_name"] == "NVIDIA Blog"]
        self.assertEqual(len(blog), 1)
        self.assertEqual(blog[0]["ticker"], "NVDA")
        self.assertEqual(blog[0]["feed_url"], "https://feeds.feedburner.com/nvidiablog")
        self.assertEqual(blog[0]["activation_at_utc"], "2026-07-20T17:50:00Z")
        self.assertEqual(set(blog[0]["allowed_hosts"]), {"feedburner.com", "nvidia.com"})


if __name__ == "__main__":
    unittest.main()
