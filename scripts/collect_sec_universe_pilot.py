from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CONTRACT_ID = "PPI-SEC-UNIVERSE-PILOT-001-R1"
SOURCE_ID = "sec_company_tickers_exchange"
SOURCE_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
HOST, PATH = "www.sec.gov", "/files/company_tickers_exchange.json"
FIELDS = ["cik", "name", "ticker", "exchange"]
EXCHANGES = {"NYSE": "NYSE", "Nasdaq": "NASDAQ", "NYSE American": "NYSE_AMERICAN"}
LIMIT, MAX_BYTES, MAX_ATTEMPTS = 500, 20_000_000, 3
TICKER = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,14}$")
EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


class PilotError(RuntimeError):
    pass


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canon(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def text(value):
    return " ".join(str(value).strip().split())


def validate_user_agent(value):
    value = text(value)
    if len(value) < 12 or not EMAIL.search(value) or "\n" in value or "\r" in value:
        raise PilotError("PPI_SEC_USER_AGENT must include an application name and monitored contact email.")
    return value


class RedirectGuard(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        parsed = urllib.parse.urlparse(newurl)
        if (parsed.scheme, parsed.hostname, parsed.path) != ("https", HOST, PATH):
            raise PilotError(f"SEC redirect left the approved endpoint: {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(user_agent):
    parsed = urllib.parse.urlparse(SOURCE_URL)
    if (parsed.scheme, parsed.hostname, parsed.path) != ("https", HOST, PATH):
        raise PilotError("SEC URL is outside the frozen allowlist.")
    request = urllib.request.Request(
        SOURCE_URL,
        headers={"User-Agent": validate_user_agent(user_agent), "Accept": "application/json", "Accept-Encoding": "gzip"},
    )
    opener = urllib.request.build_opener(RedirectGuard())
    errors = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with opener.open(request, timeout=30) as response:
                raw = response.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise PilotError("SEC response exceeded the 20 MB pilot limit.")
                encoding = (response.headers.get("Content-Encoding") or "").lower()
                payload = gzip.decompress(raw) if encoding == "gzip" else raw
                if len(payload) > MAX_BYTES or response.status != 200:
                    raise PilotError("SEC response failed the bounded size or status gate.")
                return payload, {
                    "status": response.status,
                    "content_type": response.headers.get("Content-Type"),
                    "content_encoding": response.headers.get("Content-Encoding"),
                    "etag": response.headers.get("ETag"),
                    "last_modified": response.headers.get("Last-Modified"),
                    "attempts": attempt,
                }
        except urllib.error.HTTPError as exc:
            errors.append(f"attempt={attempt}:HTTP:{exc.code}")
            if exc.code not in {429, 500, 502, 503, 504} or attempt == MAX_ATTEMPTS:
                break
        except urllib.error.URLError as exc:
            errors.append(f"attempt={attempt}:URL:{exc.reason}")
            if attempt == MAX_ATTEMPTS:
                break
        time.sleep(2**attempt)
    raise PilotError("SEC fetch failed after bounded retries: " + "; ".join(errors))


def parse_source(payload):
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise PilotError(f"SEC response is not valid JSON: {exc}") from exc
    if not isinstance(value, dict) or value.get("fields") != FIELDS or not isinstance(value.get("data"), list):
        raise PilotError("SEC fields drifted from [cik,name,ticker,exchange].")

    unique, excluded = {}, {}
    for index, row in enumerate(value["data"]):
        if not isinstance(row, list) or len(row) != 4:
            raise PilotError(f"SEC row {index} is not a four-column array.")
        cik_raw, name_raw, ticker_raw, exchange_raw = row
        exchange = EXCHANGES.get(text(exchange_raw))
        if exchange is None:
            excluded["unsupported_exchange"] = excluded.get("unsupported_exchange", 0) + 1
            continue
        if name_raw is None or ticker_raw is None:
            reason = "missing_name" if name_raw is None else "missing_ticker"
            excluded[reason] = excluded.get(reason, 0) + 1
            continue
        name, ticker = text(name_raw), text(ticker_raw).upper()
        cik_digits = re.sub(r"\D", "", text(cik_raw))
        if not name or not TICKER.fullmatch(ticker) or not cik_digits or len(cik_digits) > 10:
            excluded["invalid_row"] = excluded.get("invalid_row", 0) + 1
            continue
        normalized = {"cik": cik_digits.zfill(10), "company_name": name, "ticker": ticker, "exchange": exchange}
        key = (normalized["cik"], ticker, exchange)
        if key in unique:
            if unique[key] != normalized:
                raise PilotError(f"Conflicting SEC rows share key {key}.")
            excluded["exact_duplicate"] = excluded.get("exact_duplicate", 0) + 1
            continue
        unique[key] = normalized

    candidates = []
    for row in unique.values():
        rank = digest(f"{SOURCE_ID}|{row['cik']}|{row['ticker']}|{row['exchange']}".encode())
        candidates.append({
            "candidate_id": f"ppi-sec-seed-{rank[:24]}",
            **row,
            "identity_status": "provisional_sec_seed",
            "classification_status": "unresolved",
            "source_id": SOURCE_ID,
            "source_row_sha256": digest(canon(row)),
            "_rank": rank,
        })
    candidates.sort(key=lambda item: (item["_rank"], item["candidate_id"]))
    selected = candidates[:LIMIT]
    for item in selected:
        item.pop("_rank")
    selected.sort(key=lambda item: item["candidate_id"])
    if len(selected) != LIMIT or len({item["candidate_id"] for item in selected}) != LIMIT:
        raise PilotError("The SEC source did not produce exactly 500 unique candidates.")
    return selected, dict(sorted(excluded.items())), len(value["data"])


def snapshot(candidates):
    return b"".join(canon(item) for item in candidates)


def manifest(payload, http, candidates, excluded, source_rows, generated_at):
    snapshot_hash = digest(snapshot(candidates))
    core = {
        "schema_version": "1.0.0",
        "contract_id": CONTRACT_ID,
        "snapshot_id": f"ppi-sec-universe-pilot-{snapshot_hash[:16]}",
        "generated_at_utc": generated_at,
        "source_url": SOURCE_URL,
        "source_payload_sha256": digest(payload),
        "source_bytes": len(payload),
        "source_row_count": source_rows,
        "normalized_eligible_count": source_rows - sum(excluded.values()),
        "candidate_count": len(candidates),
        "candidate_limit": LIMIT,
        "selection_algorithm": "sha256_rank_v1",
        "snapshot_sha256": snapshot_hash,
        "exclusion_counts": excluded,
        "source_http": {key: http.get(key) for key in ("status", "content_type", "content_encoding", "etag", "last_modified")},
    }
    return {**core, "manifest_core_sha256": digest(canon(core))}


def build_manifest(*, payload, http_metadata, candidates, excluded, source_rows, generated_at):
    return manifest(payload, http_metadata, candidates, excluded, source_rows, generated_at)


def write_blocked(root, reason):
    root.mkdir(parents=True, exist_ok=True)
    blocked = {
        "schema_version": "1.0.0", "contract_id": CONTRACT_ID, "status": "blocked", "reason": reason,
        "remote_fetch_performed": False, "private_access": False, "deep_evidence": False,
        "registry_mutation": False, "generated_at_utc": now(),
    }
    (root / "blocked.json").write_text(json.dumps(blocked, indent=2, sort_keys=True) + "\n")
    (root / "report.md").write_text(f"# PPI SEC 500-instrument pilot\n\n**Status:** blocked before network access\n\nReason: {reason}\n")


def write_outputs(root, payload, http, candidates, excluded, source_rows):
    root.mkdir(parents=True, exist_ok=True)
    generated_at = now()
    snap = snapshot(candidates)
    meta = manifest(payload, http, candidates, excluded, source_rows, generated_at)
    contract_hash = digest(Path("contracts/PPI-SEC-UNIVERSE-PILOT-001-R1.json").read_bytes())
    receipt = {
        "schema_version": "1.0.0", "contract_id": CONTRACT_ID, "contract_sha256": contract_hash,
        "repository": os.environ.get("GITHUB_REPOSITORY", "local"), "run_id": os.environ.get("GITHUB_RUN_ID"),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"), "event_name": os.environ.get("GITHUB_EVENT_NAME"),
        "head_sha": os.environ.get("GITHUB_SHA"), "generated_at_utc": generated_at,
        "source_payload_sha256": meta["source_payload_sha256"], "snapshot_sha256": meta["snapshot_sha256"],
        "manifest_core_sha256": meta["manifest_core_sha256"], "remote_fetch_performed": True,
        "request_attempts": http["attempts"], "raw_payload_retained": False, "private_access": False,
        "deep_evidence": False, "registry_mutation": False, "authorized_actions": [],
    }
    (root / "sec-universe-pilot-500.jsonl").write_bytes(snap)
    (root / "manifest.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
    (root / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    (root / "report.md").write_text(
        f"# PPI SEC 500-instrument pilot\n\n- Status: success\n- Candidate count: {len(candidates)}\n"
        f"- Source rows: {source_rows}\n- Snapshot SHA-256: `{meta['snapshot_sha256']}`\n"
        "- Raw SEC payload retained: no\n- Private repository accessed: no\n"
        "- Screening or deep evidence performed: no\n"
    )
    expected = {"sec-universe-pilot-500.jsonl", "manifest.json", "receipt.json", "report.md"}
    actual = {path.name for path in root.iterdir() if path.is_file()}
    if actual != expected:
        raise PilotError(f"Unexpected output paths: {sorted(actual)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--user-agent", default=os.environ.get("PPI_SEC_USER_AGENT", ""))
    parser.add_argument("--blocked-if-missing-user-agent", action="store_true")
    args = parser.parse_args()
    if not text(args.user_agent):
        if args.blocked_if_missing_user_agent:
            write_blocked(args.output_root, "Repository variable PPI_SEC_USER_AGENT is missing; set an application name and monitored contact email.")
            return 0
        raise PilotError("PPI_SEC_USER_AGENT is required.")
    payload, http = fetch(args.user_agent)
    candidates, excluded, source_rows = parse_source(payload)
    write_outputs(args.output_root, payload, http, candidates, excluded, source_rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
