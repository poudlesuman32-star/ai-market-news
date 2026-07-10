from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.-]{0,14}$")
RFC3339_Z_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class CollectorError(ValueError):
    """Raised when fixture input cannot be converted into a safe public record."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CollectorError(message)


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CollectorError(f"{path}: invalid JSON: {exc}") from exc
    require(isinstance(value, dict), f"{path}: expected a JSON object")
    return value


def normalize_ticker(value: str) -> str:
    ticker = str(value).strip().upper()
    require(TICKER_RE.fullmatch(ticker) is not None, f"invalid ticker: {value!r}")
    return ticker


def normalize_timestamp(value: str) -> str:
    timestamp = str(value).strip()
    require(RFC3339_Z_RE.fullmatch(timestamp) is not None, f"timestamp must use UTC Z form: {value!r}")
    try:
        parsed = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise CollectorError(f"invalid timestamp: {value!r}") from exc
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def require_https_url(value: str) -> str:
    url = str(value).strip()
    parsed = urlparse(url)
    require(parsed.scheme == "https", f"URL must use https: {value!r}")
    require(bool(parsed.netloc), f"URL must include a host: {value!r}")
    require(parsed.username is None and parsed.password is None, "URL credentials are forbidden")
    return url


def normalize_text(value: str, *, field: str, maximum: int) -> str:
    text = " ".join(str(value).split())
    require(bool(text), f"{field} cannot be empty")
    require(len(text) <= maximum, f"{field} exceeds {maximum} characters")
    return text


def stable_sha256(parts: Iterable[str]) -> str:
    payload = "\x1f".join(str(part) for part in parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_public_record(
    *,
    ticker: str,
    published_at_utc: str,
    collected_at_utc: str,
    source_type: str,
    source_name: str,
    source_url: str,
    headline: str,
    summary: str,
    provider: str,
    provider_article_id: str,
    source_ticker: str,
    filing_type: str | None,
    event_identity: str,
    primary_source: bool = True,
) -> dict[str, Any]:
    normalized_ticker = normalize_ticker(ticker)
    normalized_source_ticker = normalize_ticker(source_ticker)
    published = normalize_timestamp(published_at_utc)
    collected = normalize_timestamp(collected_at_utc)
    url = require_https_url(source_url)
    source_name_value = normalize_text(source_name, field="source_name", maximum=160)
    headline_value = normalize_text(headline, field="headline", maximum=500)
    summary_value = normalize_text(summary, field="summary", maximum=4000)
    provider_value = normalize_text(provider, field="provider", maximum=80)
    provider_id_value = normalize_text(provider_article_id, field="provider_article_id", maximum=200)
    source_type_value = normalize_text(source_type, field="source_type", maximum=80)
    event_identity_value = normalize_text(event_identity, field="event_identity", maximum=500)

    source_hash = stable_sha256([url, headline_value, summary_value])
    event_id = stable_sha256([source_type_value, normalized_ticker, event_identity_value])
    record_id = stable_sha256([
        provider_value,
        provider_id_value,
        normalized_ticker,
        published,
        source_hash,
    ])

    return {
        "record_id": record_id,
        "event_id": event_id,
        "ticker": normalized_ticker,
        "published_at_utc": published,
        "collected_at_utc": collected,
        "source_type": source_type_value,
        "source_name": source_name_value,
        "source_url": url,
        "headline": headline_value,
        "summary": summary_value,
        "catalyst_tags": [],
        "ai_infrastructure_layers": [],
        "primary_source": bool(primary_source),
        "duplicate_group_id": event_id,
        "validation": "collected_untransformed",
        "provider": provider_value,
        "provider_article_id": provider_id_value,
        "source_ticker": normalized_source_ticker,
        "filing_type": filing_type,
        "language": "en",
        "source_hash": source_hash,
        "synthetic_content_used": False,
        "source_content_modified": False,
    }


def write_jsonl(records: list[dict[str, Any]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = "".join(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n" for record in records)
    output.write_text(rendered, encoding="utf-8")
