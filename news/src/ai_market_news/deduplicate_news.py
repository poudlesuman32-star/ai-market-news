from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from .collector_common import require, stable_sha256
from .normalize_news import canonicalize_url

HEADLINE_TOKEN_RE = re.compile(r"[a-z0-9]+")
HEADLINE_WINDOW_SECONDS = 6 * 60 * 60


def normalized_headline(value: str) -> str:
    return " ".join(HEADLINE_TOKEN_RE.findall(value.casefold()))


def timestamp_seconds(value: str) -> float:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()


def duplicate_pair(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if left["ticker"] != right["ticker"]:
        return False

    if left["provider"] == "sec_edgar" and right["provider"] == "sec_edgar":
        if left["provider_article_id"] == right["provider_article_id"]:
            return True

    if left["provider"] == right["provider"] and left["provider_article_id"] == right["provider_article_id"]:
        return True

    if canonicalize_url(left["source_url"]) == canonicalize_url(right["source_url"]):
        return True

    if left["source_hash"] == right["source_hash"]:
        return True

    left_headline = normalized_headline(left["headline"])
    right_headline = normalized_headline(right["headline"])
    if left_headline and left_headline == right_headline:
        difference = abs(timestamp_seconds(left["published_at_utc"]) - timestamp_seconds(right["published_at_utc"]))
        if difference <= HEADLINE_WINDOW_SECONDS:
            return True

    return False


class UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, value: int) -> int:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[max(left_root, right_root)] = min(left_root, right_root)


def repeated_value(values: list[str]) -> str | None:
    counts = Counter(values)
    repeated = sorted(value for value, count in counts.items() if count > 1)
    return repeated[0] if repeated else None


def group_identity(records: list[dict[str, Any]]) -> str:
    sec_ids = sorted(record["provider_article_id"] for record in records if record["provider"] == "sec_edgar")
    if sec_ids:
        return f"sec:{sec_ids[0]}"

    provider_ids = [f"{record['provider']}:{record['provider_article_id']}" for record in records]
    repeated_provider = repeated_value(provider_ids)
    if repeated_provider:
        return f"provider:{repeated_provider}"

    urls = [canonicalize_url(record["source_url"]) for record in records]
    repeated_url = repeated_value(urls)
    if repeated_url:
        return f"url:{repeated_url}"

    hashes = [record["source_hash"] for record in records]
    repeated_hash = repeated_value(hashes)
    if repeated_hash:
        return f"hash:{repeated_hash}"

    representative = min(
        records,
        key=lambda record: (
            record["published_at_utc"],
            normalized_headline(record["headline"]),
            record["record_id"],
        ),
    )
    return "headline:{}:{}:{}".format(
        representative["ticker"],
        normalized_headline(representative["headline"]),
        representative["published_at_utc"][:13],
    )


def deduplicate_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    record_ids = [record["record_id"] for record in records]
    require(len(record_ids) == len(set(record_ids)), "duplicate record_id detected")

    union_find = UnionFind(len(records))
    for left in range(len(records)):
        for right in range(left + 1, len(records)):
            if duplicate_pair(records[left], records[right]):
                union_find.union(left, right)

    groups: dict[int, list[dict[str, Any]]] = {}
    for index, record in enumerate(records):
        groups.setdefault(union_find.find(index), []).append(record)

    transformed: list[dict[str, Any]] = []
    for group in groups.values():
        identity = group_identity(group)
        event_id = stable_sha256([identity])
        for record in group:
            updated = dict(record)
            updated["event_id"] = event_id
            updated["duplicate_group_id"] = event_id
            transformed.append(updated)

    transformed.sort(
        key=lambda record: (
            record["published_at_utc"],
            record["ticker"],
            record["event_id"],
            record["record_id"],
        )
    )
    return transformed
