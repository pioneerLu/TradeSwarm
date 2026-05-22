#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
由权益曲线与已平仓交易列表计算回测指标。
"""

from __future__ import annotations

import csv
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


def _parse_dt(s: str) -> datetime:
    return datetime.strptime(s[:10], "%Y-%m-%d")


def compute_daily_returns(equity: Sequence[float]) -> List[float]:
    """
    返回长度与 equity 等长的日收益率序列：
    - 第 1 天收益率固定为 0.0
    - 第 i 天收益率 = equity[i]/equity[i-1] - 1
    """
    if not equity:
        return []
    out: List[float] = [0.0]
    for i in range(1, len(equity)):
        a, b = equity[i - 1], equity[i]
        if a and a > 0 and b is not None:
            out.append(b / a - 1.0)
        else:
            out.append(0.0)
    return out


def compute_cumulative_returns(equity: Sequence[float], initial_cash: float) -> List[float]:
    """累计收益（与 equity 等长）：equity/initial_cash - 1。"""
    if not equity or initial_cash <= 0:
        return [0.0 for _ in equity]
    base = float(initial_cash)
    return [(float(e) / base - 1.0) if e is not None else 0.0 for e in equity]


def max_drawdown_and_duration(equity: Sequence[float], dates: Sequence[str]) -> Dict[str, Any]:
    """最大回撤（相对历史峰值）与最长连续「未创新高」天数（近似水下时长）。"""
    if not equity:
        return {"max_drawdown": 0.0, "max_drawdown_duration_days": 0}
    peak = float(equity[0])
    max_dd = 0.0
    longest_under = 0
    current_under = 0
    peak_idx = 0
    for i, v in enumerate(equity):
        v = float(v)
        if v >= peak:
            peak = v
            peak_idx = i
            current_under = 0
        else:
            if peak > 0:
                max_dd = max(max_dd, (peak - v) / peak)
            # 自峰值日起未创新高的日历跨度
            current_under = (_parse_dt(dates[i]) - _parse_dt(dates[peak_idx])).days
            longest_under = max(longest_under, current_under)
    return {
        "max_drawdown": float(max_dd),
        "max_drawdown_duration_days": int(longest_under),
    }


def sharpe_ratio(daily_rets: Sequence[float], rf_daily: float = 0.0) -> Optional[float]:
    if len(daily_rets) < 2:
        return None
    xs = [r - rf_daily for r in daily_rets]
    mu = sum(xs) / len(xs)
    var = sum((x - mu) ** 2 for x in xs) / (len(xs) - 1)
    sd = math.sqrt(var) if var > 0 else 0.0
    if sd < 1e-12:
        return None
    return (mu / sd) * math.sqrt(252.0)


def sortino_ratio(daily_rets: Sequence[float], rf_daily: float = 0.0) -> Optional[float]:
    if len(daily_rets) < 2:
        return None
    xs = [r - rf_daily for r in daily_rets]
    mu = sum(xs) / len(xs)
    downs = [min(0.0, x) ** 2 for x in xs]
    downside_var = sum(downs) / len(downs)
    downside_sd = math.sqrt(downside_var) if downside_var > 0 else 0.0
    if downside_sd < 1e-12:
        return None
    return (mu / downside_sd) * math.sqrt(252.0)


def cagr(initial: float, final: float, calendar_days: int) -> Optional[float]:
    if initial <= 0 or calendar_days <= 0:
        return None
    years = calendar_days / 365.25
    if years <= 0:
        return None
    return (final / initial) ** (1.0 / years) - 1.0


def calmar_ratio(cagr_val: Optional[float], max_dd: float) -> Optional[float]:
    if cagr_val is None or max_dd < 1e-12:
        return None
    return cagr_val / max_dd


def summarize_closed_trades(closed: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    if not closed:
        return {
            "trade_count": 0,
            "win_rate": None,
            "avg_holding_days": None,
            "avg_trade_return_pct": None,
        }
    wins = sum(1 for t in closed if float(t.get("pnl_pct", 0)) > 0)
    hold_days = [float(t.get("holding_days", 0)) for t in closed]
    pnls = [float(t.get("pnl_pct", 0)) * 100.0 for t in closed]
    return {
        "trade_count": len(closed),
        "win_rate": wins / len(closed) if closed else None,
        "avg_holding_days": sum(hold_days) / len(hold_days) if hold_days else None,
        "avg_trade_return_pct": sum(pnls) / len(pnls) if pnls else None,
    }


def compute_metrics(
    *,
    daily_equity: Sequence[float],
    daily_dates: Sequence[str],
    initial_cash: float,
    closed_trades: Sequence[Dict[str, Any]],
    first_date: str,
    last_date: str,
) -> Dict[str, Any]:
    """daily_equity 与 daily_dates 等长。"""
    if len(daily_equity) != len(daily_dates):
        raise ValueError("daily_equity 与 daily_dates 长度不一致")

    final_equity = float(daily_equity[-1]) if daily_equity else float(initial_cash)
    total_return = (final_equity - initial_cash) / initial_cash if initial_cash > 0 else 0.0

    cal_days = (_parse_dt(last_date) - _parse_dt(first_date)).days + 1
    cagr_val = cagr(initial_cash, final_equity, cal_days)
    ann_ret = total_return * (365.25 / cal_days) if cal_days > 0 else None  # 简单年化（与 CAGR 二选一展示）

    daily_returns = compute_daily_returns(daily_equity)
    # Sharpe/Sortino 用“首日为 0 的序列”会轻微稀释样本；这里去掉首日以保持与常用定义一致。
    rets_for_risk = daily_returns[1:] if len(daily_returns) > 1 else []
    sharpe = sharpe_ratio(rets_for_risk)
    sortino = sortino_ratio(rets_for_risk)

    dd_info = max_drawdown_and_duration(daily_equity, daily_dates)
    max_dd = float(dd_info["max_drawdown"])
    calmar = calmar_ratio(cagr_val, max_dd)

    trade_stats = summarize_closed_trades(closed_trades)
    cumulative_returns = compute_cumulative_returns(daily_equity, initial_cash)

    out: Dict[str, Any] = {
        "final_equity": final_equity,
        "total_return": total_return,
        "cagr": cagr_val,
        "annualized_return": ann_ret,
        "annualized_return_simple": ann_ret,
        "daily_returns": daily_returns,
        "cumulative_returns": cumulative_returns,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "max_drawdown": max_dd,
        "max_drawdown_duration_days": dd_info["max_drawdown_duration_days"],
        **trade_stats,
    }
    return out


def align_close_prices(symbol: str, dates: Sequence[str], data_adapter: Any) -> List[Optional[float]]:
    """
    从 data_adapter.get_price(symbol, date, "close") 拉取 close，缺失则前向填充。
    返回与 dates 等长的 close 列表（可能含 None）。
    """
    out: List[Optional[float]] = []
    last: Optional[float] = None
    for d in dates:
        raw = None
        try:
            raw = data_adapter.get_price(symbol, str(d), "close")
        except Exception:
            raw = None
        v: Optional[float]
        try:
            v = float(raw) if raw is not None else None
        except Exception:
            v = None
        if v is not None and v > 0:
            last = v
        out.append(last)
    return out


def write_equity_csv(
    path: Path | str,
    *,
    dates: Sequence[str],
    equity: Sequence[float],
    initial_cash: float,
    close_prices: Optional[Sequence[Optional[float]]] = None,
) -> Path:
    """
    写统一格式 CSV：date,equity,cumulative_return,daily_return,close_price
    - cumulative_return / daily_return 为小数（非百分数）
    """
    if len(dates) != len(equity):
        raise ValueError("dates 与 equity 长度不一致")
    if close_prices is not None and len(close_prices) != len(dates):
        raise ValueError("close_prices 与 dates 长度不一致")

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    daily_returns = compute_daily_returns(equity)
    cumulative_returns = compute_cumulative_returns(equity, initial_cash)

    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["date", "equity", "cumulative_return", "daily_return", "close_price"],
        )
        w.writeheader()
        for i, d in enumerate(dates):
            cp = close_prices[i] if close_prices is not None else None
            w.writerow(
                {
                    "date": str(d)[:10],
                    "equity": float(equity[i]) if equity[i] is not None else "",
                    "cumulative_return": float(cumulative_returns[i]),
                    "daily_return": float(daily_returns[i]) if i < len(daily_returns) else 0.0,
                    "close_price": float(cp) if cp is not None else "",
                }
            )
    return p
