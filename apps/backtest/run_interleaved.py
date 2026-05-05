from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TARGET = REPO_ROOT / "scripts" / "runtime" / "run_interleaved_backtest.py"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Agent-QC interleaved backtest: agent decides daily, QC executes, real results feed back.",
    )
    parser.add_argument("--symbol", type=str, default="NVDA")
    parser.add_argument("--start", type=str, default="2025-01-02")
    parser.add_argument("--end", type=str, default="2025-01-10")
    parser.add_argument("--db", type=str, default=str(Path("storage") / "db" / "memory.db"))
    parser.add_argument("--lean-workspace", type=str, default=str(REPO_ROOT / "lean_workspace"))
    parser.add_argument("--project-name", type=str, default="TradeSwarm")
    parser.add_argument("--initial-cash", type=float, default=100_000.0)
    parser.add_argument("--enabled-analysts", type=str, default="market,news,sentiment,fundamentals")
    parser.add_argument("--experiment-id", type=str, default=None)
    parser.add_argument("--use-db-reports-only", action="store_true", default=True)
    parser.add_argument("--no-db-reports-only", action="store_false", dest="use_db_reports_only")
    parser.add_argument("--report-output-root", type=str, default=None)
    parser.add_argument("--graph-dump", type=str, default=None)
    parser.add_argument("--max-research-debate-rounds", type=int, default=None)
    parser.add_argument("--max-risk-debate-rounds", type=int, default=None)
    parser.add_argument("--llm-profile", type=str, default=None)
    parser.add_argument("--llm-model", type=str, default=None)
    parser.add_argument("--llm-temperature", type=float, default=None)
    parser.add_argument("--strategy-skills-mode", choices=("reflect", "all", "off"), default=None)
    parser.add_argument("--strategy-skills-fallback-mode", choices=("all", "off"), default=None)
    parser.add_argument(
        "--force-strategy-skill",
        choices=(
            "strong_uptrend_skill",
            "range_bound_skill",
            "downtrend_skill",
            "high_vol_uncertain_skill",
        ),
        default=None,
    )
    parser.add_argument("-v", "--verbose", action="store_true")
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
