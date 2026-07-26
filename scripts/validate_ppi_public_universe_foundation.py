#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = ROOT / "config/ppi_public_source_inventory.json"
CONTRACT_PATH = ROOT / "contracts/PPI-UNIVERSE-US-COMMON-001-R1.json"
SCHEMA_PATH = ROOT / "schemas/ppi_public_universe_foundation.schema.json"

EXPECTED_SOURCE_REPOSITORY = "poudlesuman32-star/ai-market-news"
EXPECTED_SOURCE_REPOSITORY_ID = 1290414659
EXPECTED_CONTRACT_ID = "PPI-UNIVERSE-US-COMMON-001-R1"
EXPECTED_BATCH3_TICKERS = [
    "AAPL", "MU", "NVDA", "AMD", "AVGO", "INTC",
    "TSM", "ARM", "QCOM", "MRVL", "GFS", "TXN",
]
EXPECTED_CATEGORIES = [
    "expectation_history",
    "independent_recognition",
    "market_time_series",
    "specialized_contract_data",
]
EXPECTED_LIFECYCLE_STATES = [
    "universe_member", "eligible", "screened", "deep_evidence_queued",
    "collecting", "evidence_ready", "private_pending", "accepted",
    "rejected", "deferred", "inactive",
]
EXPECTED_APPLICABILITY_STATES = [
    "available", "valid_empty", "not_applicable", "insufficient_history",
    "temporarily_unavailable", "provider_failure", "invalid_payload",
]
DANGEROUS_AUTHORITIES = [
    "remote_fetch",
    "provider_execution",
    "deep_evidence_collection",
    "private_dispatch",
    "billing_budget_mutation",
    "registry_mutation",
    "production",
    "publication",
    "broker",
    "orders",
    "trading",
    "mmm_raw_data",
    "r12",
]


class FoundationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise FoundationError(message)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path.relative_to(ROOT)} must contain a JSON object")
    return value


def git_blob_sha1(path: Path) -> str:
    content = path.read_bytes()
    header = f"blob {len(content)}\0".encode("ascii")
    return hashlib.sha1(header + content).hexdigest()


def validate_inventory(inventory: dict[str, Any]) -> dict[str, int]:
    require(inventory.get("inventory_id") == "PPI-PUBLIC-SOURCE-INVENTORY-001-R1", "source inventory identity mismatch")
    require(inventory.get("repository") == EXPECTED_SOURCE_REPOSITORY, "source inventory repository mismatch")
    require(inventory.get("repository_id") == EXPECTED_SOURCE_REPOSITORY_ID, "source inventory repository ID mismatch")
    require(inventory.get("private_source_dependency") is False, "private source dependency is forbidden")
    require(inventory.get("authorized_actions") == [], "source inventory authorized_actions must remain empty")

    sources = inventory.get("sources")
    require(isinstance(sources, list) and sources, "source inventory must contain sources")
    require(len({item.get("source_id") for item in sources if isinstance(item, dict)}) == len(sources), "source IDs must be unique")

    approved_universe = []
    approved_identifier = []
    approved_screening = []
    for source in sources:
        require(isinstance(source, dict), "every source inventory entry must be an object")
        for key in (
            "source_id", "operations", "cost_class", "access_model", "rate_limit",
            "public_runner_allowed", "requires_secret", "requires_private_secret",
            "raw_publication_allowed", "derived_metrics_allowed",
            "private_handoff_required", "licensing_status", "approved",
        ):
            require(key in source, f"source entry missing {key}")
        operations = source["operations"]
        require(isinstance(operations, list) and operations, f"{source['source_id']} operations must be nonempty")
        if source["approved"]:
            require(source["public_runner_allowed"] is True, f"approved source {source['source_id']} is not public-runner compatible")
            require(source["requires_private_secret"] is False, f"approved source {source['source_id']} requires a private secret")
            require(source["cost_class"] == "free", f"approved foundation source {source['source_id']} is not free")
        if source["approved"] and "listing_universe" in operations:
            require(source["access_model"] in {"bulk", "multi_symbol"}, "approved universe source must be bulk or multi-symbol")
            approved_universe.append(source)
        if source["approved"] and "security_identifier_mapping" in operations:
            approved_identifier.append(source)
        if source["approved"] and "lightweight_screening" in operations:
            approved_screening.append(source)

    require(approved_universe, "no approved free public universe source")
    require(approved_identifier, "no approved free public identifier source")
    require(not approved_screening, "screening must remain blocked until provider and terms review")

    authority = inventory.get("authority")
    require(isinstance(authority, dict), "source inventory authority is missing")
    for key in DANGEROUS_AUTHORITIES:
        require(authority.get(key) is False, f"source inventory authority unexpectedly enabled: {key}")

    return {
        "source_count": len(sources),
        "approved_universe_source_count": len(approved_universe),
        "approved_identifier_source_count": len(approved_identifier),
        "approved_screening_source_count": len(approved_screening),
    }


def validate_frozen_batch3(contract: dict[str, Any]) -> dict[str, str]:
    frozen = contract.get("frozen_batch3")
    require(isinstance(frozen, dict), "frozen batch-3 boundary is missing")
    require(frozen.get("tickers") == EXPECTED_BATCH3_TICKERS, "batch-3 ticker scope changed")
    require(frozen.get("categories") == EXPECTED_CATEGORIES, "batch-3 category scope changed")
    require(frozen.get("bundle_count") == 48, "batch-3 bundle count changed")
    require(frozen.get("path_count") == 50, "batch-3 path count changed")

    pinned = frozen.get("pinned_files")
    require(isinstance(pinned, list) and len(pinned) == 3, "exactly three batch-3 files must be pinned")
    result: dict[str, str] = {}
    for item in pinned:
        require(isinstance(item, dict), "pinned file entry must be an object")
        path = ROOT / str(item.get("path", ""))
        expected = item.get("git_blob_sha1")
        require(path.is_file(), f"pinned file is missing: {path.relative_to(ROOT)}")
        actual = git_blob_sha1(path)
        require(actual == expected, f"frozen batch-3 file changed: {path.relative_to(ROOT)}")
        result[str(path.relative_to(ROOT))] = actual

    acquisition = load_json(ROOT / pinned[0]["path"])
    collector = load_json(ROOT / pinned[1]["path"])
    batch = load_json(ROOT / pinned[2]["path"])
    require(acquisition.get("contract_id") == "PPI-R11-PUBLIC-ACQUISITION-003-R2", "frozen acquisition contract ID changed")
    require(acquisition.get("cumulative_tickers") == EXPECTED_BATCH3_TICKERS, "frozen acquisition tickers changed")
    require(acquisition.get("categories") == EXPECTED_CATEGORIES, "frozen acquisition categories changed")
    require(acquisition.get("exact_success_package") == {
        "bundle_count": 48,
        "manifest_count": 1,
        "receipt_count": 1,
        "path_count": 50,
    }, "frozen acquisition package counts changed")
    require(collector.get("contract_id") == "PPI-PUBLIC-COLLECTOR-003-R2", "frozen collector ID changed")
    require(collector.get("expected_bundle_count") == 48, "frozen collector bundle count changed")
    require(collector.get("expected_path_count") == 50, "frozen collector path count changed")
    require(batch.get("cumulative_tickers") == EXPECTED_BATCH3_TICKERS, "frozen batch config tickers changed")
    require(batch.get("expected_bundle_count") == 48, "frozen batch config bundle count changed")
    require(batch.get("expected_path_count") == 50, "frozen batch config path count changed")
    return result


def validate_contract(contract: dict[str, Any]) -> dict[str, str]:
    require(contract.get("contract_id") == EXPECTED_CONTRACT_ID, "universe contract identity mismatch")
    require(contract.get("status") == "draft_foundation", "universe contract status mismatch")
    require(contract.get("source_repository") == EXPECTED_SOURCE_REPOSITORY, "universe contract source repository mismatch")
    require(contract.get("source_repository_id") == EXPECTED_SOURCE_REPOSITORY_ID, "universe contract source repository ID mismatch")
    require(contract.get("authorized_actions") == [], "universe contract authorized_actions must remain empty")

    scope = contract.get("universe_scope")
    require(isinstance(scope, dict), "universe scope is missing")
    require(scope.get("eligible_exchanges") == ["NYSE", "NASDAQ", "NYSE_AMERICAN"], "eligible exchange scope changed")
    require(scope.get("included_asset_types") == ["common_stock"], "common-stock universe scope changed")
    require(scope.get("separately_contracted_asset_types") == ["adr"], "ADR must remain separately contracted")
    require("etf" in scope.get("excluded_asset_types", []), "ETF exclusion is missing")

    identity = contract.get("identity_layers")
    require(identity == {
        "primary": "instrument_id",
        "security_level_external": "figi",
        "issuer_level_external": "cik",
        "time_bounded_alias": "ticker",
    }, "stable identity layers changed")

    require(contract.get("lifecycle_states") == EXPECTED_LIFECYCLE_STATES, "lifecycle states changed")
    require(contract.get("applicability_states") == EXPECTED_APPLICABILITY_STATES, "applicability states changed")

    scheduler = contract.get("foundation_scheduler")
    require(isinstance(scheduler, dict), "foundation scheduler policy is missing")
    require(scheduler.get("workflow_path") == ".github/workflows/ppi-public-universe-foundation.yml", "foundation workflow path mismatch")
    require(scheduler.get("schedule") == "17 6 * * 1", "foundation schedule mismatch")
    require(scheduler.get("remote_fetch_authorized") is False, "foundation scheduler remote fetch is forbidden")
    require(scheduler.get("provider_credentials_authorized") is False, "foundation scheduler provider credentials are forbidden")
    require(scheduler.get("private_repository_access_authorized") is False, "foundation scheduler private access is forbidden")
    require(scheduler.get("safe_readiness_artifact_only") is True, "foundation scheduler must retain only safe readiness output")

    authority = contract.get("authority")
    require(isinstance(authority, dict), "universe contract authority is missing")
    for key in DANGEROUS_AUTHORITIES:
        if key in authority:
            require(authority.get(key) is False, f"universe contract authority unexpectedly enabled: {key}")

    return validate_frozen_batch3(contract)


def validate_schema(schema: dict[str, Any]) -> dict[str, int]:
    require(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema", "schema draft mismatch")
    definitions = schema.get("$defs")
    require(isinstance(definitions, dict), "schema definitions are missing")
    require(definitions.get("lifecycle_state", {}).get("enum") == EXPECTED_LIFECYCLE_STATES, "schema lifecycle states changed")
    require(definitions.get("applicability_state", {}).get("enum") == EXPECTED_APPLICABILITY_STATES, "schema applicability states changed")

    instrument = definitions.get("instrument")
    require(isinstance(instrument, dict), "instrument schema is missing")
    required = instrument.get("required")
    require(isinstance(required, list), "instrument required fields are missing")
    for field in (
        "instrument_id", "current_symbol", "exchange", "asset_type", "status",
        "cik", "figi", "first_seen_at", "last_confirmed_at", "symbol_history",
        "source_id", "source_timestamp",
    ):
        require(field in required, f"instrument schema missing required field: {field}")

    event = definitions.get("universe_event")
    snapshot = definitions.get("snapshot_manifest")
    require(isinstance(event, dict), "universe event schema is missing")
    require(isinstance(snapshot, dict), "snapshot manifest schema is missing")
    return {
        "definition_count": len(definitions),
        "instrument_required_field_count": len(required),
    }


def write_report(output_root: Path, report: dict[str, Any]) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "readiness.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# PPI public universe foundation",
        "",
        f"- Status: **{report['status']}**",
        f"- Contract: `{report['contract_id']}`",
        f"- Approved universe sources: `{report['inventory']['approved_universe_source_count']}`",
        f"- Approved identifier sources: `{report['inventory']['approved_identifier_source_count']}`",
        f"- Approved screening sources: `{report['inventory']['approved_screening_source_count']}`",
        f"- Frozen batch-3 files verified: `{len(report['frozen_batch3_git_blobs'])}`",
        "- Remote fetch performed: `False`",
        "- Provider credentials used: `False`",
        "- Private repository accessed: `False`",
        "- Deep evidence collected: `False`",
        "- Private dispatch performed: `False`",
        "- Registry mutation performed: `False`",
        "",
        "The next implementation gate is the SEC 500-instrument ingestion prototype. "
        "It remains separate from this no-network foundation scheduler.",
    ]
    (output_root / "readiness.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the public-only PPI universe foundation")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=ROOT / "runtime/ppi-public-universe-foundation",
    )
    args = parser.parse_args()

    inventory = load_json(INVENTORY_PATH)
    contract = load_json(CONTRACT_PATH)
    schema = load_json(SCHEMA_PATH)

    inventory_summary = validate_inventory(inventory)
    frozen = validate_contract(contract)
    schema_summary = validate_schema(schema)

    report = {
        "schema_version": "1.0.0",
        "status": "foundation_ready",
        "contract_id": EXPECTED_CONTRACT_ID,
        "inventory": inventory_summary,
        "schema": schema_summary,
        "frozen_batch3_git_blobs": frozen,
        "authority": {
            "remote_fetch": False,
            "provider_execution": False,
            "deep_evidence_collection": False,
            "private_dispatch": False,
            "billing_budget_mutation": False,
            "registry_mutation": False,
            "production": False,
            "publication": False,
            "broker": False,
            "orders": False,
            "trading": False,
            "mmm_raw_data": False,
            "r12": False,
        },
    }
    write_report(args.output_root, report)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FoundationError as exc:
        raise SystemExit(str(exc)) from exc
