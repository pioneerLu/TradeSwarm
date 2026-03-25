#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
从已有的 backtest_results/daily_results/*.json 转换为 QuantConnect 信号格式。

用于在无 memory.db 或未跑 run_signal_export 时，用历史回测结果快速生成 signals.json 供 QuantConnect 测试。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


def convert(daily_dir: Path, symbol: str, output_path: Path) -> dict:
    """从 daily_results 目录转换"""
    signals = {}
    by_execution_date = {}

    for f in sorted(daily_dir.glob("*.json")):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                day = json.load(fp)
        except Exception as e:
            print(f"[WARN] 跳过 {f.name}: {e}")
            continue

        trade_date = day.get("date", f.stem)
        mo = day.get("market_open") or {}
        exec_log = (mo.get("execution_log") or [{}])[0]
        trades = (mo.get("portfolio_state") or {}).get("recent_trades") or []
        pos = mo.get("current_position")
        reason = exec_log.get("reason", "")

        action = "HOLD"
        target_pct = 0.0
        execution_date = trade_date

        if "当天已执行过交易" in (reason or ""):
            action = "HOLD"
            execution_date = None
        elif "区间内持有" in (reason or "") or "风险决策为 HOLD" in (reason or ""):
            action = "HOLD"
            execution_date = None
        elif trades:
            t = trades[-1]
            execution_date = t.get("date", trade_date)
            if t.get("action") == "buy":
                action = "BUY"
                total = (mo.get("portfolio_state") or {}).get("total_value") or 100000
                amount = t.get("amount", 0)
                target_pct = amount / total if total else 0.1
            elif t.get("action") == "sell":
                action = "SELL"
        elif pos and pos.get("shares", 0) > 0 and not trades:
            execution_date = pos.get("entry_date", trade_date)
            action = "BUY"
            target_pct = (pos.get("market_value") or 0) / 100000

        sig = {
            "date": trade_date,
            "symbol": symbol,
            "execution_date": execution_date,
            "action": action,
            "target_pct": round(target_pct, 4),
            "stop_loss": None,
            "take_profit": None,
            "entry_type": "MKT_OPEN",
            "entry_price": None,
            "reason": reason[:200] if reason else "",
            "is_exploratory": "探索" in (reason or ""),
        }
        signals[trade_date] = sig
        if execution_date and action in ("BUY", "SELL"):
            by_execution_date[str(execution_date)] = sig

    result = {
        "symbol": symbol,
        "start_date": min(signals.keys()) if signals else "",
        "end_date": max(signals.keys()) if signals else "",
        "signals": signals,
        "by_execution_date": by_execution_date,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    print(f"[OK] 已写入 {output_path}")
    return result


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--daily-dir", type=str, default="backtest_results/daily_results")
    p.add_argument("--symbol", type=str, default="NVDA")
    p.add_argument("--output", type=str, default="qc_signals/signals.json")
    args = p.parse_args()
    convert(Path(args.daily_dir), args.symbol, Path(args.output))


if __name__ == "__main__":
    main()
