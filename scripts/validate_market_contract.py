#!/usr/bin/env python3
"""Command-line validator for public Iteration 16 market artifacts."""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from scripts.contract_common import load_object, require
from scripts.validate_latest_pointer import validate_latest_pointer
from scripts.validate_market_csv import validate_market_csv
from scripts.validate_market_manifest import validate_market_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols-config", type=Path, default=Path("config/iteration_16_symbols.json"))
    parser.add_argument("--collection-config", type=Path, default=Path("config/iteration_16_collection.json"))
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--market-root", type=Path, default=Path("."))
    parser.add_argument("--latest", type=Path)
    parser.add_argument("--today")
    args = parser.parse_args()

    try:
        require(any((args.csv, args.manifest, args.latest)), "provide --csv, --manifest, or --latest")
        symbols = load_object(args.symbols_config)
        collection = load_object(args.collection_config)
        today = date.fromisoformat(args.today) if args.today else None
        if args.csv:
            validate_market_csv(args.csv, symbols_config=symbols, collection_config=collection, today=today)
        if args.manifest:
            validate_market_manifest(
                args.manifest,
                market_root=args.market_root,
                symbols_config=symbols,
                collection_config=collection,
                today=today,
            )
        if args.latest:
            validate_latest_pointer(args.latest, collection_config=collection)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"market contract validation failed: {exc}") from exc
    print("market contract validation passed")


if __name__ == "__main__":
    main()
