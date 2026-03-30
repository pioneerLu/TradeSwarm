from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TARGET = REPO_ROOT / "scripts" / "runtime" / "run_automated_backtest.py"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the local backtest flow from prepared analyst data."
    )
    parser.add_argument("--source", choices=("export", "daily"), default="export")
    parser.add_argument("--symbol", type=str, default="NVDA")
    parser.add_argument("--start", type=str, default="2025-01-01")
    parser.add_argument("--end", type=str, default="2025-03-01")
    parser.add_argument("--db", type=str, default=str(Path("storage") / "db" / "memory.db"))
    parser.add_argument("--enabled-analysts", type=str, default=None)
    parser.add_argument("--experiment-id", type=str, default=None)
    parser.add_argument("--report-output-root", type=str, default=str(Path("storage") / "reports"))
    parser.add_argument("--graph-dump", type=str, default=str(Path("storage") / "graph_dumps"))
    parser.add_argument("--output-dir", type=str, default=str(Path("storage") / "backtests"))
    parser.add_argument("--daily-dir", type=str, default=str(Path("backtest_results") / "daily_results"))
    parser.add_argument("--skip-backtest", action="store_true")
    parser.add_argument("--max-research-debate-rounds", type=int, default=None)
    parser.add_argument("--max-risk-debate-rounds", type=int, default=None)
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
