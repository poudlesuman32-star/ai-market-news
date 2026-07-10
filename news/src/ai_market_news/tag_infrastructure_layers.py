from __future__ import annotations

from typing import Any

INFRASTRUCTURE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("semiconductors", ("semiconductor", "chip", "gpu", "dram", "nand", "memory")),
    ("compute", ("compute", "accelerator", "gpu", "training cluster", "inference")),
    ("data_centers", ("data center", "datacenter", "hyperscaler", "cloud infrastructure")),
    ("networking", ("networking", "ethernet", "interconnect", "switching", "optical")),
    ("storage", ("storage", "nand", "ssd", "hard drive")),
    ("power_and_cooling", ("power", "cooling", "liquid cooling", "electrical infrastructure")),
    ("software_platforms", ("software platform", "developer platform", "ai platform", "cloud software")),
)


def tag_infrastructure_layers(record: dict[str, Any]) -> list[str]:
    haystack = " ".join(
        str(value).casefold()
        for value in (
            record.get("headline", ""),
            record.get("summary", ""),
        )
    )
    return [layer for layer, keywords in INFRASTRUCTURE_RULES if any(keyword in haystack for keyword in keywords)]
