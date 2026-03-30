#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Offline batch builder for analyst_summaries.

This script consumes analyst_reports already stored in memory.db and writes
7-trading-day rolling summaries into analyst_summaries. It now supports:

- date range runs via --start/--end
- explicit date lists via --dates
- analyst filtering via --types
- symbol filtering via --symbol
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tradingagents.agents.post_close.history_maintainer import create_history_maintainer_node
from tradingagents.agents.utils.memory_db_helper import MemoryDBHelper
from tradingagents.graph.utils import load_llm_from_config

ALL_ANALYST_TYPES: Tuple[str, ...] = ("market", "news", "fundamentals", "sentiment")


def parse_analyst_types_arg(types_str: str | None) -> Tuple[str, ...]:
    """Parse --types into a stable, deduplicated tuple."""
    if not types_str or not types_str.strip():
        return ALL_ANALYST_TYPES

    requested = [item.strip().lower() for item in types_str.split(",") if item.strip()]
    valid = set(ALL_ANALYST_TYPES)
    for item in requested:
        if item not in valid:
            raise ValueError(
                f"Unknown analyst type: {item}. Valid options: {', '.join(ALL_ANALYST_TYPES)}"
            )

    return tuple(name for name in ALL_ANALYST_TYPES if name in requested)


def get_symbols_and_dates(db: MemoryDBHelper) -> List[Tuple[str, str]]:
    """Return distinct (symbol, trade_date) pairs from analyst_reports."""
    conn = db._get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT DISTINCT symbol, trade_date
        FROM analyst_reports
        WHERE report_content IS NOT NULL AND report_content != ''
        ORDER BY trade_date ASC, symbol ASC
        """
    )
    rows = cursor.fetchall()
    cursor.close()
    return [(row[0], row[1]) for row in rows]


def filter_by_range(
    items: Iterable[Tuple[str, str]],
    start: str | None,
    end: str | None,
) -> List[Tuple[str, str]]:
    """Filter (symbol, trade_date) pairs by date range."""
    result: List[Tuple[str, str]] = []
    for symbol, trade_date in items:
        if start and trade_date < start:
            continue
        if end and trade_date > end:
            continue
        result.append((symbol, trade_date))
    return result


def filter_by_explicit_dates(
    items: Iterable[Tuple[str, str]],
    dates: Sequence[str] | None,
) -> List[Tuple[str, str]]:
    """Filter (symbol, trade_date) pairs by explicit date list."""
    if not dates:
        return list(items)
    allowed = set(dates)
    return [(symbol, trade_date) for symbol, trade_date in items if trade_date in allowed]


def _format_dates_for_log(dates: Sequence[str] | None) -> str:
    if not dates:
        return "(not set)"
    return ", ".join(dates)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Offline batch builder for analyst_summaries."
    )
    parser.add_argument(
        "--db",
        type=str,
        default="memory.db",
        help="Path to memory.db.",
    )
    parser.add_argument(
        "--start",
        type=str,
        default=None,
        help="Start date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--end",
        type=str,
        default=None,
        help="End date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--dates",
        type=str,
        default=None,
        help="Comma-separated explicit trade dates. When set, --start/--end are ignored.",
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default=None,
        help="Only build summaries for the given symbol.",
    )
    parser.add_argument(
        "--types",
        type=str,
        default=None,
        help="Comma-separated analyst list, e.g. market or market,news.",
    )
    parser.add_argument(
        "--sleep-ms",
        type=int,
        default=500,
        help="Extra delay in milliseconds after each (symbol, date) run.",
    )
    args = parser.parse_args()

    try:
        analyst_types = parse_analyst_types_arg(args.types)
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        sys.exit(1)

    explicit_dates = None
    if args.dates:
        explicit_dates = sorted({item.strip() for item in args.dates.split(",") if item.strip()})
        if not explicit_dates:
            print("[ERROR] --dates resolved to an empty list.")
            sys.exit(1)

    db_path = Path(args.db)
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    print("=" * 80)
    print("Offline analyst_summaries batch builder")
    print("=" * 80)
    print(f"DB: {db_path}")
    if explicit_dates:
        print(f"Dates: {_format_dates_for_log(explicit_dates)}")
    else:
        print(f"Date range: {args.start or '(min)'} ~ {args.end or '(max)'}")
    print(f"Symbol: {args.symbol or '(all)'}")
    print(f"Analysts: {', '.join(analyst_types)}")

    with MemoryDBHelper(str(db_path)) as db:
        llm = load_llm_from_config()
        node = create_history_maintainer_node(
            llm=llm,
            db_helper=db,
            analyst_types=analyst_types,
        )

        all_items = get_symbols_and_dates(db)
        if not all_items:
            print("[WARN] No analyst_reports found. Nothing to build.")
            return

        if args.symbol:
            all_items = [(symbol, trade_date) for symbol, trade_date in all_items if symbol == args.symbol]
            if not all_items:
                print(f"[WARN] No analyst_reports found for symbol={args.symbol}.")
                return

        if explicit_dates:
            items = filter_by_explicit_dates(all_items, explicit_dates)
        else:
            items = filter_by_range(all_items, start=args.start, end=args.end)

        if not items:
            print("[WARN] No analyst_reports matched the selected filters.")
            return

        total = len(items)
        print(f"[INFO] Total (symbol, date) pairs to process: {total}")

        for idx, (symbol, trade_date) in enumerate(items, 1):
            print(f"\n[{idx}/{total}] {symbol} @ {trade_date}")

            state = {
                "company_of_interest": symbol,
                "trade_date": trade_date,
                "trading_session": "post_close",
                "messages": [],
                "current_position": None,
                "portfolio_state": None,
            }

            try:
                result = node(state)
                log = result.get("history_maintainer_log", [])
                if not log:
                    print("  [WARN] No analyst summary work was attempted.")
                else:
                    for item in log:
                        analyst = item.get("analyst_type", "?")
                        status = item.get("status", "?")
                        if status == "ok":
                            print(f"  [OK] {analyst}: summary updated")
                        elif status == "skipped_existing":
                            print(f"  [SKIP] {analyst}: summary already exists")
                        elif status == "skipped_no_reports":
                            print(f"  [SKIP] {analyst}: no source reports found")
                        else:
                            print(f"  [ERROR] {analyst}: {item.get('error', status)}")
            except Exception as exc:  # noqa: BLE001
                print(f"  [ERROR] History Maintainer failed: {exc}")

            if args.sleep_ms and args.sleep_ms > 0:
                time.sleep(args.sleep_ms / 1000.0)


if __name__ == "__main__":
    main()
