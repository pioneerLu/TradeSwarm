#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
自动化平台回测脚本（适合每日定时运行，无需手动复制到网页）

解决「每次复制到 Algorithm Lab 难以长期测试」的问题：
- 网页版：需手动粘贴 EMBEDDED_SIGNALS，不适合自动化
- 本脚本：Lean CLI 本地读取 signals.json，可完全自动化

流程：
  1. 导出信号（run_signal_export 或 convert_daily_results_to_signals）
  2. 复制到 Lean 项目 signals/
  3. 执行 lean backtest
  4. 保存摘要（可定时任务、CI 集成）

前置（首次）：
  lean login
  lean init  # 或按 docs/LEAN_LOCAL_SETUP.md 完成
  Docker 运行

用法：
  # 从 memory.db analyst_reports 导出并回测（推荐）
  python run_automated_backtest.py --source export --start 2025-01-01 --end 2025-03-01

  # 从已有 daily_results 转换并回测
  python run_automated_backtest.py --source daily --daily-dir backtest_results/daily_results

  # 仅导出+复制，不执行回测
  python run_automated_backtest.py --source export --skip-backtest
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


def ensure_signals_from_export(args) -> Path:
    """从 analyst_reports 导出信号到 qc_signals/signals.json"""
    signals_out = REPO_ROOT / "qc_signals" / "signals.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "runtime" / "run_signal_export.py"),
            "--symbol", args.symbol,
            "--start", args.start,
            "--end", args.end,
            "--db", args.db,
            "--output", "qc_signals",
        ],
        cwd=str(REPO_ROOT),
    )
    if proc.returncode != 0:
        print("[ERROR] run_signal_export 失败")
        sys.exit(1)
    return signals_out


def ensure_signals_from_daily(args) -> Path:
    """从 daily_results 转换到 qc_signals/signals.json"""
    daily_dir = Path(args.daily_dir)
    signals_out = REPO_ROOT / "qc_signals" / "signals.json"
    if not daily_dir.exists():
        print(f"[ERROR] daily_results 不存在: {daily_dir}")
        sys.exit(1)
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "runtime" / "convert_daily_results_to_signals.py"),
            "--daily-dir", str(daily_dir),
            "--output", str(signals_out),
        ],
        cwd=str(REPO_ROOT),
    )
    if proc.returncode != 0:
        print("[ERROR] 信号转换失败")
        sys.exit(1)
    return signals_out


def run_lean_backtest(args) -> bool:
    """执行 Lean 回测，返回是否成功"""
    lean_workspace = REPO_ROOT / "lean_workspace"
    qc_dir = REPO_ROOT / "quantconnect"

    # 优先使用 lean_workspace（run_lean_no_proxy 场景）
    if (lean_workspace / "TradeSwarm").exists():
        print("[INFO] 使用 lean_workspace/TradeSwarm，通过 run_lean_no_proxy.ps1 执行")
        cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File",
               str(REPO_ROOT / "scripts" / "run_lean_no_proxy.ps1"),
               "backtest", "TradeSwarm", "--download-data"]
        cwd = REPO_ROOT
    elif qc_dir.exists() and (qc_dir / "main.py").exists():
        print("[INFO] 使用 quantconnect/ 项目直接回测")
        cmd = ["lean", "backtest", str(qc_dir), "--download-data"]
        cwd = REPO_ROOT
    else:
        print("[ERROR] 未找到 Lean 项目。请完成 lean init 并创建 TradeSwarm，或确保 quantconnect/ 目录存在。")
        print("  参见: docs/LEAN_LOCAL_SETUP.md")
        return False

    print(f"[RUN] {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=str(cwd))
    return proc.returncode == 0


def main():
    p = argparse.ArgumentParser(description="自动化平台回测（Lean CLI 本地，可每日定时）")
    p.add_argument("--source", choices=["export", "daily"], default="export",
                   help="信号来源: export=从 memory.db 导出, daily=从 daily_results 转换")
    p.add_argument("--symbol", type=str, default="NVDA")
    p.add_argument("--start", type=str, default="2025-01-01", help="日期区间（--source export 时有效）")
    p.add_argument("--end", type=str, default="2025-03-01")
    p.add_argument("--db", type=str, default="memory.db")
    p.add_argument("--daily-dir", type=str, default="backtest_results/daily_results",
                   help="daily_results 目录（--source daily 时有效）")
    p.add_argument("--skip-backtest", action="store_true", help="仅导出+复制，不执行 lean backtest")
    p.add_argument("--output-dir", type=str, default="backtest_summaries",
                   help="摘要保存目录")
    args = p.parse_args()

    print("=" * 60)
    print("TradeSwarm 自动化平台回测")
    print("=" * 60)

    # 1. 获取信号
    if args.source == "export":
        signals_out = ensure_signals_from_export(args)
        signals_source = f"run_signal_export ({args.start}~{args.end})"
    else:
        signals_out = ensure_signals_from_daily(args)
        signals_source = str(args.daily_dir)
    print(f"[OK] 信号已就绪: {signals_out}")

    # 2. 复制到 Lean 项目（支持 quantconnect/ 与 lean_workspace/TradeSwarm 两种布局）
    dests = [
        REPO_ROOT / "quantconnect" / "signals" / "signals.json",
        REPO_ROOT / "lean_workspace" / "TradeSwarm" / "signals" / "signals.json",
    ]
    for dest in dests:
        parent = dest.parent
        if dest.parent.parent.exists():  # quantconnect/ 或 lean_workspace/TradeSwarm/ 存在
            parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(signals_out, dest)
            print(f"[OK] 已复制到 {dest}")

    # 3. 同步 main.py 到 lean_workspace（若存在）
    lean_main = REPO_ROOT / "lean_workspace" / "TradeSwarm" / "main.py"
    if lean_main.parent.exists():
        shutil.copy(REPO_ROOT / "quantconnect" / "main.py", lean_main)
        print(f"[OK] 已同步 main.py 到 lean_workspace/TradeSwarm")

    # 4. 执行回测
    if args.skip_backtest:
        print("[SKIP] 跳过 lean backtest")
        success = True
    else:
        success = run_lean_backtest(args)
        if not success:
            sys.exit(1)

    # 5. 保存摘要
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
        "backtest_success": success,
        "engine": "QuantConnect (lean backtest --download-data)",
    }
    summary_path = out_dir / f"backtest_{ts}.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"[OK] 摘要已保存: {summary_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
