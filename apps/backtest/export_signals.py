from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TARGET = REPO_ROOT / "scripts" / "runtime" / "run_signal_export.py"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export ratings or backtest signals from prepared analyst data."
    )
    parser.add_argument("--symbol", type=str, default="NVDA")
    parser.add_argument("--start", type=str, default="2025-01-01")
    parser.add_argument("--end", type=str, default="2025-03-01")
    parser.add_argument("--dates", type=str, default=None, metavar="DATE1,DATE2,...")
    parser.add_argument("--db", type=str, default=str(Path("storage") / "db" / "memory.db"))
    parser.add_argument("--output", type=str, default=str(Path("storage") / "signals"))
    parser.add_argument(
        "--enabled-analysts",
        type=str,
        default="market,news,sentiment,fundamentals",
    )
    parser.add_argument("--experiment-id", type=str, default=None)
    parser.add_argument("--report-output-root", type=str, default=str(Path("storage") / "reports"))
    parser.add_argument("--graph-dump", type=str, default=str(Path("storage") / "graph_dumps"))
    parser.add_argument("--export-mode", choices=("backtest", "rating"), default="backtest")
    parser.add_argument("--max-research-debate-rounds", type=int, default=None)
    parser.add_argument("--max-risk-debate-rounds", type=int, default=None)
    parser.add_argument("--simulate-portfolio", action="store_true")
    parser.add_argument("--initial-cash", type=float, default=100_000.0)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--use-db-reports-only", action="store_true", default=True)
    parser.add_argument("--no-db-reports-only", action="store_false", dest="use_db_reports_only")
    args = parser.parse_args()

    forwarded = [str(TARGET)]
    for key, value in vars(args).items():
        flag = f"--{key.replace('_', '-')}"
        if isinstance(value, bool):
            if value:
                forwarded.append(flag)
        elif value is not None:
            forwarded.extend([flag, str(value)])

    sys.argv = forwarded
    runpy.run_path(str(TARGET), run_name="__main__")


if __name__ == "__main__":
    main()
