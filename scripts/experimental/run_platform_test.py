#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TradeSwarm 平台回测测试脚本

1. 转换 daily_results → signals.json
2. 复制到 quantconnect/signals/
3. 调用 lean backtest（QuantConnect 平台数据，无回退、无模拟）

前置（需在首次使用前手动完成）：
  lean login
  lean init  # 在空目录执行，创建 lean.json
  Docker 可用
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


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--skip-backtest", action="store_true", help="仅转换+复制信号，不执行 lean backtest")
    args = p.parse_args()

    # 1. 转换信号
    daily_dir = REPO_ROOT / "backtest_results_v0" / "daily_results"
    signals_out = REPO_ROOT / "qc_signals" / "signals.json"
    if not daily_dir.exists():
        print(f"[ERROR] daily_results 不存在: {daily_dir}")
        sys.exit(1)

    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "runtime" / "convert_daily_results_to_signals.py"),
         "--daily-dir", str(daily_dir),
         "--output", str(signals_out)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(f"[ERROR] 信号转换失败: {proc.stderr or proc.stdout}")
        sys.exit(1)
    print("[OK] 信号已转换 -> qc_signals/signals.json")

    # 2. 复制到 quantconnect/signals/
    qc_signals_dir = REPO_ROOT / "quantconnect" / "signals"
    qc_signals_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(signals_out, qc_signals_dir / "signals.json")
    print("[OK] 信号已复制 -> quantconnect/signals/signals.json")

    # 3. 运行 lean backtest（QuantConnect 平台数据，无回退、无模拟）
    if args.skip_backtest:
        print("[SKIP] 跳过 lean backtest（--skip-backtest）")
    else:
        # 前置：lean login，lean init，Docker 可用
        qc_dir = REPO_ROOT / "quantconnect"
        lean_cmd = ["lean", "backtest", str(qc_dir), "--download-data"]
        print(f"[RUN] {' '.join(lean_cmd)}")
        proc = subprocess.run(lean_cmd, cwd=str(REPO_ROOT))
        if proc.returncode != 0:
            print("[ERROR] lean backtest 失败。前置：lean login、lean init、Docker")
            sys.exit(1)

    # 4. 保存测试摘要
    out_dir = REPO_ROOT / "test_results"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary = {
        "timestamp": ts,
        "signals_source": str(daily_dir),
        "signals_output": str(signals_out),
        "qc_signals": str(qc_signals_dir / "signals.json"),
        "backtest_engine": "QuantConnect (lean backtest --download-data)",
        "data_source": "QuantConnect 平台（无回退、无模拟）",
    }
    summary_path = out_dir / f"platform_test_{ts}.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"[OK] 测试摘要已保存: {summary_path}")


if __name__ == "__main__":
    main()
