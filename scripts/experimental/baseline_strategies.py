#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基准策略：BH / MA 金叉死叉 / MACD 金叉死叉 / KDJ 金叉死叉。
指标在完整 OHLC DataFrame 上预计算；decide 仅读取截至当日的行，避免前瞻。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

import pandas as pd


@dataclass
class StrategyContext:
    """单日决策上下文。"""

    symbol: str
    trade_date: str  # YYYY-MM-DD
    df: pd.DataFrame  # 含预计算指标，index 为 DatetimeIndex
    day_index: int  # 在 trading_dates 中的下标
    trading_dates: List[str]


class BaselineStrategy(Protocol):
    name: str
    min_bars: int

    def decide(self, ctx: StrategyContext) -> Dict[str, Any]: ...


def _ts(df: pd.DataFrame, date_str: str) -> pd.Timestamp:
    t = pd.to_datetime(date_str)
    if df.index.tz is not None:
        if t.tzinfo is None:
            t = t.tz_localize(df.index.tz)
        else:
            t = t.tz_convert(df.index.tz)
    return t


def _row_at(df: pd.DataFrame, date_str: str) -> Optional[pd.Series]:
    """取截止日所在行（必须存在于 index）。"""
    ts = _ts(df, date_str)
    if ts not in df.index:
        return None
    return df.loc[ts]


def _prev_row(df: pd.DataFrame, date_str: str) -> Optional[pd.Series]:
    ts = _ts(df, date_str)
    if ts not in df.index:
        return None
    pos = df.index.get_loc(ts)
    if isinstance(pos, slice):
        pos = pos.start
    if int(pos) == 0:
        return None
    return df.iloc[int(pos) - 1]


def add_ma_columns(df: pd.DataFrame, fast: int, slow: int) -> pd.DataFrame:
    c = df["Close"].astype(float)
    out = df.copy()
    out["ma_fast"] = c.rolling(window=fast, min_periods=fast).mean()
    out["ma_slow"] = c.rolling(window=slow, min_periods=slow).mean()
    return out


def add_macd_columns(df: pd.DataFrame, fast: int, slow: int, signal: int) -> pd.DataFrame:
    c = df["Close"].astype(float)
    ema_f = c.ewm(span=fast, adjust=False).mean()
    ema_s = c.ewm(span=slow, adjust=False).mean()
    macd_line = ema_f - ema_s
    macd_sig = macd_line.ewm(span=signal, adjust=False).mean()
    out = df.copy()
    out["macd_line"] = macd_line
    out["macd_signal"] = macd_sig
    return out


def add_kdj_columns(
    df: pd.DataFrame,
    *,
    n: int = 9,
    k_smooth: int = 3,
    d_smooth: int = 3,
) -> pd.DataFrame:
    """
    计算 KDJ（随机指标）列：kdj_k, kdj_d, kdj_j。

    约定：
    - RSV = (Close - LLV(n)) / (HHV(n) - LLV(n)) * 100
    - K = SMA(RSV, k_smooth)；D = SMA(K, d_smooth)
      使用常见的「递推平滑」形式（近似国内软件 SMA）：
        X_t = (m-1)/m * X_{t-1} + 1/m * V_t
      初始化 K_0 = D_0 = 50
    - J = 3K - 2D
    """
    if n <= 0 or k_smooth <= 0 or d_smooth <= 0:
        raise ValueError("KDJ 参数必须为正整数")

    out = df.copy()
    c = out["Close"].astype(float)
    h = out["High"].astype(float)
    l = out["Low"].astype(float)

    llv = l.rolling(window=n, min_periods=n).min()
    hhv = h.rolling(window=n, min_periods=n).max()
    denom = (hhv - llv).replace(0.0, pd.NA)
    rsv = ((c - llv) / denom) * 100.0
    rsv = rsv.clip(lower=0.0, upper=100.0)

    k = pd.Series(index=out.index, dtype="float64")
    d = pd.Series(index=out.index, dtype="float64")
    prev_k = 50.0
    prev_d = 50.0
    alpha_k = 1.0 / float(k_smooth)
    alpha_d = 1.0 / float(d_smooth)
    for idx, v in rsv.items():
        if pd.isna(v):
            k.loc[idx] = pd.NA
            d.loc[idx] = pd.NA
            continue
        prev_k = (1.0 - alpha_k) * prev_k + alpha_k * float(v)
        prev_d = (1.0 - alpha_d) * prev_d + alpha_d * prev_k
        k.loc[idx] = prev_k
        d.loc[idx] = prev_d

    j = 3.0 * k - 2.0 * d
    out["kdj_k"] = k
    out["kdj_d"] = d
    out["kdj_j"] = j
    return out


def min_bars_ma(fast: int, slow: int) -> int:
    return max(fast, slow)


def min_bars_macd(slow: int, signal: int) -> int:
    # EMA 近似稳定需若干根；保守取 slow + signal + 缓冲
    return slow + signal + 5


def min_bars_kdj(n: int, k_smooth: int, d_smooth: int) -> int:
    # RSV 需要 n 根；K/D 递推平滑再给一点缓冲
    return n + k_smooth + d_smooth + 5


class BuyHoldStrategy:
    name = "bh"
    min_bars = 1

    def decide(self, ctx: StrategyContext) -> Dict[str, Any]:
        if ctx.day_index == 0:
            return {
                "action": "BUY",
                "target_pct": 1.0,
                "entry_type": "MKT_OPEN",
                "entry_price": None,
                "reason": "benchmark BH: 区间首日满仓买入并持有",
            }
        return {
            "action": "HOLD",
            "target_pct": 0.0,
            "entry_type": "MKT_OPEN",
            "entry_price": None,
            "reason": "benchmark BH: 持有",
        }


class MaCrossStrategy:
    name = "ma"

    def __init__(self, fast: int, slow: int) -> None:
        self.fast = fast
        self.slow = slow
        self.min_bars = min_bars_ma(fast, slow)

    def decide(self, ctx: StrategyContext) -> Dict[str, Any]:
        row = _row_at(ctx.df, ctx.trade_date)
        prev = _prev_row(ctx.df, ctx.trade_date)
        if row is None or prev is None:
            return _hold("MA: 无足够 K 线")
        mf = row.get("ma_fast")
        ms = row.get("ma_slow")
        pf = prev.get("ma_fast")
        ps = prev.get("ma_slow")
        if any(pd.isna(x) for x in (mf, ms, pf, ps)):
            return _hold("MA: 指标未就绪")

        # 上穿：前一日 fast<=slow，当日 fast>slow
        if float(pf) <= float(ps) and float(mf) > float(ms):
            return {
                "action": "BUY",
                "target_pct": 1.0,
                "entry_type": "MKT_OPEN",
                "entry_price": None,
                "reason": "benchmark MA: 金叉满仓",
            }
        if float(pf) >= float(ps) and float(mf) < float(ms):
            return {
                "action": "SELL",
                "target_pct": 0.0,
                "entry_type": "MKT_OPEN",
                "entry_price": None,
                "reason": "benchmark MA: 死叉清仓",
            }
        return _hold("benchmark MA: 无交叉")


class MacdStrategy:
    name = "macd"

    def __init__(self, fast: int, slow: int, signal: int) -> None:
        self.fast = fast
        self.slow = slow
        self.signal = signal
        self.min_bars = min_bars_macd(slow, signal)

    def decide(self, ctx: StrategyContext) -> Dict[str, Any]:
        row = _row_at(ctx.df, ctx.trade_date)
        prev = _prev_row(ctx.df, ctx.trade_date)
        if row is None or prev is None:
            return _hold("MACD: 无足够 K 线")
        m = row.get("macd_line")
        s = row.get("macd_signal")
        pm = prev.get("macd_line")
        ps = prev.get("macd_signal")
        if any(pd.isna(x) for x in (m, s, pm, ps)):
            return _hold("MACD: 指标未就绪")

        if float(pm) <= float(ps) and float(m) > float(s):
            return {
                "action": "BUY",
                "target_pct": 1.0,
                "entry_type": "MKT_OPEN",
                "entry_price": None,
                "reason": "benchmark MACD: 线上穿信号线，满仓",
            }
        if float(pm) >= float(ps) and float(m) < float(s):
            return {
                "action": "SELL",
                "target_pct": 0.0,
                "entry_type": "MKT_OPEN",
                "entry_price": None,
                "reason": "benchmark MACD: 线下穿信号线，清仓",
            }
        return _hold("benchmark MACD: 无交叉")


class KdjStrategy:
    name = "kdj"

    def __init__(self, n: int = 9, k_smooth: int = 3, d_smooth: int = 3) -> None:
        self.n = n
        self.k_smooth = k_smooth
        self.d_smooth = d_smooth
        self.min_bars = min_bars_kdj(n, k_smooth, d_smooth)

    def decide(self, ctx: StrategyContext) -> Dict[str, Any]:
        row = _row_at(ctx.df, ctx.trade_date)
        prev = _prev_row(ctx.df, ctx.trade_date)
        if row is None or prev is None:
            return _hold("KDJ: 无足够 K 线")
        k = row.get("kdj_k")
        d = row.get("kdj_d")
        pk = prev.get("kdj_k")
        pd_ = prev.get("kdj_d")
        if any(pd.isna(x) for x in (k, d, pk, pd_)):
            return _hold("KDJ: 指标未就绪")

        if float(pk) <= float(pd_) and float(k) > float(d):
            return {
                "action": "BUY",
                "target_pct": 1.0,
                "entry_type": "MKT_OPEN",
                "entry_price": None,
                "reason": "benchmark KDJ: K 上穿 D（金叉），满仓",
            }
        if float(pk) >= float(pd_) and float(k) < float(d):
            return {
                "action": "SELL",
                "target_pct": 0.0,
                "entry_type": "MKT_OPEN",
                "entry_price": None,
                "reason": "benchmark KDJ: K 下穿 D（死叉），清仓",
            }
        return _hold("benchmark KDJ: 无交叉")


def _hold(reason: str) -> Dict[str, Any]:
    return {
        "action": "HOLD",
        "target_pct": 0.0,
        "entry_type": "MKT_OPEN",
        "entry_price": None,
        "reason": reason,
    }


def build_strategy(
    name: str,
    ma_fast: int,
    ma_slow: int,
    macd_fast: int,
    macd_slow: int,
    macd_signal: int,
    *,
    kdj_n: int = 9,
    kdj_k_smooth: int = 3,
    kdj_d_smooth: int = 3,
) -> BaselineStrategy:
    n = name.strip().lower()
    if n in ("bh", "buyhold", "buy_and_hold"):
        return BuyHoldStrategy()
    if n in ("ma",):
        return MaCrossStrategy(ma_fast, ma_slow)
    if n in ("macd",):
        return MacdStrategy(macd_fast, macd_slow, macd_signal)
    if n in ("kdj",):
        return KdjStrategy(kdj_n, kdj_k_smooth, kdj_d_smooth)
    raise ValueError(f"未知策略: {name}（支持 bh, ma, macd, kdj）")
