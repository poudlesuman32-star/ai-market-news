from __future__ import annotations

from typing import Any

CATALYST_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("earnings", ("earnings", "quarterly report", "10-q", "10-k", "results")),
    ("guidance", ("guidance", "outlook", "forecast")),
    ("contracts", ("contract", "award", "purchase order")),
    ("partnerships", ("partnership", "collaboration", "strategic alliance")),
    ("customer_announcements", ("customer announcement", "customer commitment", "customer agreement")),
    ("capacity", ("capacity", "expansion", "new fab", "manufacturing facility")),
    ("supply_constraints", ("shortage", "supply constraint", "constrained supply")),
    ("pricing", ("pricing", "price increase", "average selling price")),
    ("backlog", ("backlog", "bookings")),
    ("capex", ("capex", "capital expenditure", "hyperscaler spending", "infrastructure spending")),
    ("launches", ("launch", "introduces", "unveils", "new product")),
    ("regulation", ("regulation", "regulatory", "antitrust", "export control")),
    ("financing", ("financing", "debt offering", "equity offering", "credit facility")),
    ("management_events", ("chief executive", "chief financial", "ceo", "cfo", "management change")),
)


def tag_catalysts(record: dict[str, Any]) -> list[str]:
    haystack = " ".join(
        str(value).casefold()
        for value in (
            record.get("headline", ""),
            record.get("summary", ""),
            record.get("filing_type", "") or "",
        )
    )
    return [tag for tag, keywords in CATALYST_RULES if any(keyword in haystack for keyword in keywords)]
