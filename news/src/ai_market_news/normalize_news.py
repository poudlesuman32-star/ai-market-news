from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .collector_common import CollectorError, normalize_text, normalize_timestamp, normalize_ticker, require, require_https_url

TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}
STRING_FIELDS = (
    "record_id",
    "event_id",
    "source_type",
    "source_name",
    "source_url",
    "headline",
    "summary",
    "duplicate_group_id",
    "validation",
    "provider",
    "provider_article_id",
    "language",
    "source_hash",
)
REQUIRED_FIELDS = {
    "record_id",
    "event_id",
    "ticker",
    "published_at_utc",
    "collected_at_utc",
    "source_type",
    "source_name",
    "source_url",
    "headline",
    "summary",
    "catalyst_tags",
    "ai_infrastructure_layers",
    "primary_source",
    "duplicate_group_id",
    "validation",
    "provider",
    "provider_article_id",
    "source_ticker",
    "filing_type",
    "language",
    "source_hash",
    "synthetic_content_used",
    "source_content_modified",
}


def canonicalize_url(value: str) -> str:
    url = require_https_url(value)
    parts = urlsplit(url)
    filtered_query = []
    for key, item in parse_qsl(parts.query, keep_blank_values=True):
        lowered = key.lower()
        if lowered in TRACKING_QUERY_KEYS or any(lowered.startswith(prefix) for prefix in TRACKING_QUERY_PREFIXES):
            continue
        filtered_query.append((key, item))
    filtered_query.sort()
    path = parts.path or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(filtered_query), ""))


def normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    require(isinstance(record, dict), "news record must be an object")
    missing = REQUIRED_FIELDS - set(record)
    require(not missing, f"news record missing required fields: {sorted(missing)}")
    extra = set(record) - REQUIRED_FIELDS
    require(not extra, f"news record contains unexpected fields: {sorted(extra)}")

    normalized = dict(record)
    for field in STRING_FIELDS:
        value = normalized[field]
        require(isinstance(value, str), f"{field} must be a string")
        normalized[field] = value.strip()
        require(bool(normalized[field]), f"{field} cannot be empty")

    normalized["ticker"] = normalize_ticker(str(normalized["ticker"]))
    normalized["source_ticker"] = normalize_ticker(str(normalized["source_ticker"]))
    normalized["published_at_utc"] = normalize_timestamp(str(normalized["published_at_utc"]))
    normalized["collected_at_utc"] = normalize_timestamp(str(normalized["collected_at_utc"]))
    normalized["source_url"] = canonicalize_url(str(normalized["source_url"]))
    normalized["source_name"] = normalize_text(str(normalized["source_name"]), field="source_name", maximum=160)
    normalized["headline"] = normalize_text(str(normalized["headline"]), field="headline", maximum=500)
    normalized["summary"] = normalize_text(str(normalized["summary"]), field="summary", maximum=4000)

    for field in ("catalyst_tags", "ai_infrastructure_layers"):
        values = normalized[field]
        require(isinstance(values, list), f"{field} must be a list")
        require(all(isinstance(value, str) and value.strip() for value in values), f"{field} must contain non-empty strings")
        normalized[field] = sorted(set(value.strip() for value in values))

    require(isinstance(normalized["primary_source"], bool), "primary_source must be boolean")
    require(normalized["filing_type"] is None or isinstance(normalized["filing_type"], str), "filing_type must be string or null")
    if isinstance(normalized["filing_type"], str):
        normalized["filing_type"] = normalized["filing_type"].strip().upper()
    require(normalized["language"] == "en", "only English public records are supported in this gate")
    require(normalized["synthetic_content_used"] is False, "synthetic content must fail closed")
    require(normalized["source_content_modified"] is False, "modified source content must fail closed")
    require(normalized["validation"] in {"collected_untransformed", "transformed_valid"}, "unsupported validation state")
    return normalized


def read_jsonl(paths: Iterable[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in paths:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CollectorError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
            records.append(normalize_record(value))
    return records
