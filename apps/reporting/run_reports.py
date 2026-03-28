from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.runtime.run_signal_export import run_signal_export


def main() -> None:
    parser = argparse.ArgumentParser(description="Run reporting flow and persist report artifacts.")
    parser.add_argument("--symbol", type=str, default="NVDA")
    parser.add_argument("--start", type=str, default="2025-01-01")
    parser.add_argument("--end", type=str, default="2025-03-01")
    parser.add_argument("--dates", type=str, default=None)
    parser.add_argument("--db", type=str, default=str(Path("storage") / "db" / "memory.db"))
    parser.add_argument("--enabled-analysts", type=str, default="market,news,sentiment,fundamentals")
    parser.add_argument("--experiment-id", type=str, default=None)
    parser.add_argument("--report-output-root", type=str, default=str(Path("storage") / "reports"))
    parser.add_argument("--graph-dump", type=str, default=str(Path("storage") / "graph_dumps"))
    args = parser.parse_args()

    dates_override = None
    if args.dates:
        dates_override = sorted({d.strip() for d in args.dates.split(",") if d.strip()})

    run_signal_export(
        symbol=args.symbol,
        start_date=args.start,
        end_date=args.end,
        db_path=args.db,
        output_dir=str(Path("storage") / "signals"),
        use_db_reports_only=True,
        export_mode="rating",
        trading_dates_override=dates_override,
        graph_dump_dir=args.graph_dump,
        enabled_analysts=[x.strip() for x in args.enabled_analysts.split(",") if x.strip()],
        experiment_id=args.experiment_id,
        report_output_root=args.report_output_root,
    )


if __name__ == "__main__":
    main()
