from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.runtime.run_signal_export import run_signal_export


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ablation experiments with a dynamic analyst set.")
    parser.add_argument("--symbol", type=str, default="NVDA")
    parser.add_argument("--start", type=str, default="2025-01-01")
    parser.add_argument("--end", type=str, default="2025-03-01")
    parser.add_argument("--db", type=str, default="storage/db/memory.db")
    parser.add_argument("--enabled-analysts", type=str, required=True, help="Comma-separated analyst list")
    parser.add_argument("--experiment-id", type=str, default=None)
    parser.add_argument("--max-research-debate-rounds", type=int, default=None)
    parser.add_argument("--max-risk-debate-rounds", type=int, default=None)
    args = parser.parse_args()

    enabled = [x.strip() for x in args.enabled_analysts.split(",") if x.strip()]
    run_signal_export(
        symbol=args.symbol,
        start_date=args.start,
        end_date=args.end,
        db_path=args.db,
        output_dir="storage/signals",
        use_db_reports_only=True,
        export_mode="backtest",
        enabled_analysts=enabled,
        experiment_id=args.experiment_id,
        report_output_root="storage/reports",
        graph_dump_dir="storage/graph_dumps",
        max_research_debate_rounds=args.max_research_debate_rounds,
        max_risk_debate_rounds=args.max_risk_debate_rounds,
    )


if __name__ == "__main__":
    main()
