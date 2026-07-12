from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .collector_common import CollectorError, require

GATE_VERSION = "live-primary-mixed-v2"
REQUIRED_PROVIDERS = ("sec_edgar", "official_company_source")
SUPPORTED_EVENTS = {"workflow_dispatch", "schedule"}


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CollectorError(f"cannot read valid JSON: {path}") from exc
    require(isinstance(value, dict), f"expected JSON object: {path}")
    return value


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def enforce_live_preview_gate(*, receipt_path: Path, report_path: Path) -> dict[str, Any]:
    receipt = read_json(receipt_path)
    report = read_json(report_path)

    request_counts = receipt.get("request_counts")
    provider_counts = receipt.get("provider_counts")
    failures = receipt.get("provider_failures")
    require(isinstance(request_counts, dict), "receipt request_counts must be an object")
    require(isinstance(provider_counts, dict), "receipt provider_counts must be an object")
    require(isinstance(failures, list), "receipt provider_failures must be a list")

    workflow_event = report.get("workflow_event")
    scheduled = workflow_event == "schedule"
    checks = {
        "collection_mode_live_primary_sources": receipt.get("collection_mode") == "live_primary_sources",
        "workflow_event_supported": workflow_event in SUPPORTED_EVENTS,
        "schedule_mode_consistent": report.get("schedule_enabled") is scheduled,
        "sec_network_requests_recorded": int(request_counts.get("sec", 0)) > 0,
        "official_company_network_requests_recorded": int(request_counts.get("official_company_sources", 0)) > 0,
        "accepted_sec_record_present": int(provider_counts.get("sec_edgar", 0)) > 0,
        "accepted_official_company_record_present": int(provider_counts.get("official_company_source", 0)) > 0,
        "provider_failures_empty": failures == [],
        "accepted_events_present": int(report.get("accepted_event_count", 0)) > 0,
        "rejected_events_empty": int(report.get("rejected_event_count", 0)) == 0,
        "publication_disabled": report.get("published_to_repository") is False,
        "external_writes_disabled": report.get("external_writes_enabled") is False,
    }
    exclusion_reasons = sorted(name for name, passed in checks.items() if not passed)
    qualifies = not exclusion_reasons

    report.update(
        {
            "live_primary_gate_version": GATE_VERSION,
            "required_accepted_providers": list(REQUIRED_PROVIDERS),
            "live_primary_countability_checks": checks,
            "qualification_exclusion_reasons": exclusion_reasons,
            "this_run_qualifies": qualifies,
        }
    )
    write_json_atomic(report_path, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Enforce the mixed-provider live primary-source preview gate")
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    report = enforce_live_preview_gate(receipt_path=args.receipt, report_path=args.report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
