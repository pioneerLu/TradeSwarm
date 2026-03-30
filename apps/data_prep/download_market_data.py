from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TARGET = REPO_ROOT / "scripts" / "runtime" / "download_yf_for_lean.py"


def default_output_for(symbol: str) -> str:
    return str(Path("storage") / "market_data" / f"{symbol.lower()}_daily.csv")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download local market data for backtesting."
    )
    parser.add_argument("--symbol", type=str, default="NVDA")
    parser.add_argument("--start", type=str, default="2025-01-01")
    parser.add_argument("--end", type=str, default="2025-03-01")
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    forwarded = [str(TARGET)]
    forwarded.extend(["--symbol", args.symbol])
    forwarded.extend(["--start", args.start])
    forwarded.extend(["--end", args.end])
    forwarded.extend(["--output", args.output or default_output_for(args.symbol)])

    sys.argv = forwarded
    runpy.run_path(str(TARGET), run_name="__main__")


if __name__ == "__main__":
    main()
