#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""将 cycle_reflections 批量 upsert 到持久化 Chroma（与 HybridMemory 召回一致）。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tradingagents.agents.utils.hybrid_memory import backfill_cycle_reflections_to_chroma  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="Backfill Chroma from cycle_reflections")
    p.add_argument("--db", type=str, default=str(REPO_ROOT / "storage" / "db" / "memory.db"))
    p.add_argument("--symbol", type=str, default=None, help="仅该标的；默认全表（同 cycle_type）")
    p.add_argument("--limit", type=int, default=2000)
    p.add_argument("--config", type=str, default=str(REPO_ROOT / "config" / "config.yaml"))
    args = p.parse_args()
    cfg = Path(args.config) if args.config else None
    n = backfill_cycle_reflections_to_chroma(
        args.db,
        symbol=args.symbol,
        limit=args.limit,
        config_path=cfg,
    )
    print(f"[OK] upserted {n} reflection rows into Chroma")


if __name__ == "__main__":
    main()
