from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TARGET = REPO_ROOT / "scripts" / "experimental" / "run_history_maintainer_batch.py"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build analyst_summaries into the local SQLite database."
    )
    parser.add_argument("--db", type=str, default=str(Path("storage") / "db" / "memory.db"))
    parser.add_argument("--start", type=str, default=None)
    parser.add_argument("--end", type=str, default=None)
    parser.add_argument("--dates", type=str, default=None, metavar="DATE1,DATE2,...")
    parser.add_argument("--symbol", type=str, default=None)
    parser.add_argument("--types", type=str, default=None, metavar="TYPES")
    parser.add_argument("--sleep-ms", type=int, default=500, metavar="MS")
    args = parser.parse_args()

    forwarded = [str(TARGET)]
    for key, value in vars(args).items():
        flag = f"--{key.replace('_', '-')}"
        if value is not None:
            forwarded.extend([flag, str(value)])

    sys.argv = forwarded
    runpy.run_path(str(TARGET), run_name="__main__")


if __name__ == "__main__":
    main()
