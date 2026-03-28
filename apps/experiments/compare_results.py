from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two experiment result files.")
    parser.add_argument("left", type=str)
    parser.add_argument("right", type=str)
    args = parser.parse_args()

    left = json.loads(Path(args.left).read_text(encoding="utf-8"))
    right = json.loads(Path(args.right).read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "left_experiment": left.get("experiment_id"),
                "right_experiment": right.get("experiment_id"),
                "left_dates": sorted((left.get("signals") or left.get("by_date") or {}).keys()),
                "right_dates": sorted((right.get("signals") or right.get("by_date") or {}).keys()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

