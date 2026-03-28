#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Automated local backtest entrypoint for TradeSwarm.

Flow:
1. Export signals from prepared analyst data, or convert existing daily results
2. Copy signals into the local Lean/QuantConnect project
3. Run `lean backtest`
4. Persist a compact summary JSON for experiment tracking
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def ensure_signals_from_export(args: argparse.Namespace) -> Path:
    """Export signals from prepared analyst reports into qc_signals/signals.json."""
    signals_out = REPO_ROOT / "qc_signals" / "signals.json"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "runtime" / "run_signal_export.py"),
        "--symbol",
        args.symbol,
        "--start",
        args.start,
        "--end",
        args.end,
        "--db",
        args.db,
        "--output",
        "qc_signals",
    ]
    if args.enabled_analysts:
        cmd.extend(["--enabled-analysts", args.enabled_analysts])
    if args.experiment_id:
        cmd.extend(["--experiment-id", args.experiment_id])
    if args.report_output_root:
        cmd.extend(["--report-output-root", args.report_output_root])

    proc = subprocess.run(cmd, cwd=str(REPO_ROOT))
    if proc.returncode != 0:
        print("[ERROR] run_signal_export failed")
        sys.exit(1)
    return signals_out


def ensure_signals_from_daily(args: argparse.Namespace) -> Path:
    """Convert daily results into qc_signals/signals.json."""
    daily_dir = Path(args.daily_dir)
    signals_out = REPO_ROOT / "qc_signals" / "signals.json"
    if not daily_dir.exists():
        print(f"[ERROR] daily_results directory does not exist: {daily_dir}")
        sys.exit(1)
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "runtime" / "convert_daily_results_to_signals.py"),
            "--daily-dir",
            str(daily_dir),
            "--output",
            str(signals_out),
        ],
        cwd=str(REPO_ROOT),
    )
    if proc.returncode != 0:
        print("[ERROR] signal conversion failed")
        sys.exit(1)
    return signals_out


def run_lean_backtest() -> bool:
    """Run Lean backtest and return whether it succeeded."""
    lean_workspace = REPO_ROOT / "lean_workspace"
    qc_dir = REPO_ROOT / "quantconnect"

    if (lean_workspace / "TradeSwarm").exists():
        print("[INFO] Using lean_workspace/TradeSwarm via run_lean_no_proxy.ps1")
        cmd = [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(REPO_ROOT / "scripts" / "run_lean_no_proxy.ps1"),
            "backtest",
            "TradeSwarm",
            "--download-data",
        ]
        cwd = REPO_ROOT
    elif qc_dir.exists() and (qc_dir / "main.py").exists():
        print("[INFO] Using quantconnect/ project directly")
        cmd = ["lean", "backtest", str(qc_dir), "--download-data"]
        cwd = REPO_ROOT
    else:
        print("[ERROR] Lean project not found. See docs/LEAN_LOCAL_SETUP.md")
        return False

    print(f"[RUN] {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=str(cwd))
    return proc.returncode == 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Automated TradeSwarm local backtest runner.")
    parser.add_argument(
        "--source",
        choices=["export", "daily"],
        default="export",
        help="Signal source: export from prepared data or convert daily results",
    )
    parser.add_argument("--symbol", type=str, default="NVDA")
    parser.add_argument("--start", type=str, default="2025-01-01")
    parser.add_argument("--end", type=str, default="2025-03-01")
    parser.add_argument("--db", type=str, default="memory.db")
    parser.add_argument("--enabled-analysts", type=str, default=None)
    parser.add_argument("--experiment-id", type=str, default=None)
    parser.add_argument("--report-output-root", type=str, default="storage/reports")
    parser.add_argument("--daily-dir", type=str, default="backtest_results/daily_results")
    parser.add_argument("--skip-backtest", action="store_true")
    parser.add_argument("--output-dir", type=str, default="storage/backtests")
    args = parser.parse_args()

    print("=" * 60)
    print("TradeSwarm automated local backtest")
    print("=" * 60)

    if args.source == "export":
        signals_out = ensure_signals_from_export(args)
        signals_source = f"run_signal_export ({args.start}~{args.end})"
    else:
        signals_out = ensure_signals_from_daily(args)
        signals_source = str(args.daily_dir)
    print(f"[OK] Signals ready: {signals_out}")

    dests = [
        REPO_ROOT / "quantconnect" / "signals" / "signals.json",
        REPO_ROOT / "lean_workspace" / "TradeSwarm" / "signals" / "signals.json",
    ]
    for dest in dests:
        if dest.parent.parent.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(signals_out, dest)
            print(f"[OK] Copied to {dest}")

    lean_main = REPO_ROOT / "lean_workspace" / "TradeSwarm" / "main.py"
    if lean_main.parent.exists():
        shutil.copy(REPO_ROOT / "quantconnect" / "main.py", lean_main)
        print("[OK] Synced quantconnect/main.py into lean_workspace/TradeSwarm")

    if args.skip_backtest:
        print("[SKIP] Skipped lean backtest")
        success = True
    else:
        success = run_lean_backtest()
        if not success:
            sys.exit(1)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary = {
        "timestamp": ts,
        "source": args.source,
        "signals_source": signals_source,
        "signals_file": str(signals_out),
        "start": args.start if args.source == "export" else None,
        "end": args.end if args.source == "export" else None,
        "symbol": args.symbol,
        "enabled_analysts": args.enabled_analysts,
        "experiment_id": args.experiment_id,
        "backtest_success": success,
        "engine": "QuantConnect (lean backtest --download-data)",
    }
    summary_path = out_dir / f"backtest_{ts}.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"[OK] Saved summary: {summary_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
