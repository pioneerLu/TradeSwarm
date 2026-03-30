from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TARGET = REPO_ROOT / "scripts" / "experimental" / "build_analyst_dataset.py"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build analyst_reports into the local SQLite database."
    )
    parser.add_argument("--start", type=str, default=None)
    parser.add_argument("--end", type=str, default="2025-03-01")
    parser.add_argument("--days", type=int, default=0)
    parser.add_argument("--trading-days", type=int, default=None, metavar="N")
    parser.add_argument("--symbol", type=str, default="NVDA")
    parser.add_argument("--db", type=str, default=str(Path("storage") / "db" / "memory.db"))
    parser.add_argument("--output", type=str, default="")
    parser.add_argument("--no-export", action="store_true")
    parser.add_argument("--export-only", action="store_true")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--dates", type=str, default=None, metavar="DATE1,DATE2,...")
    parser.add_argument("--only-missing", action="store_true")
    parser.add_argument("--types", type=str, default=None, metavar="TYPES")
    parser.add_argument("--llm-read-timeout", type=float, default=None, metavar="SEC")
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
