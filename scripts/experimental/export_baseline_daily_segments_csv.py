#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Export baseline (non-agent) strategies daily performance into ONE CSV (GBK).

Segments:
- 2024-01-01 ~ 2024-03-01
- 2024-10-01 ~ 2025-01-01
- 2025-01-01 ~ 2025-03-01

Strategies (fixed):
- BH (buy & hold)
- MA cross windows: 5/20, 10/30, 20/50 by default
- MACD cross
- KDJ cross (default 9,3,3)

Output: a single wide CSV (GBK) plus an optional PNG chart.
"""

from __future__ import annotations

import argparse
import pickle
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd

import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.experimental.baseline_metrics import (  # noqa: E402
    compute_cumulative_returns,
    compute_daily_returns,
)
from scripts.experimental.baseline_strategies import (  # noqa: E402
    add_ma_columns,
    add_macd_columns,
    add_kdj_columns,
    build_strategy,
)
from tradingagents.core.data.loader import setup_proxy  # noqa: E402
from tradingagents.core.data_adapter import DataAdapter  # noqa: E402


SEGMENTS: List[Tuple[str, str, str]] = [
    ("seg1_2024-01-01_2024-03-01", "2024-01-01", "2024-03-01"),
    ("seg2_2024-10-01_2025-01-01", "2024-10-01", "2025-01-01"),
    ("seg3_2025-01-01_2025-03-01", "2025-01-01", "2025-03-01"),
]
DEFAULT_MA_WINDOWS: List[Tuple[int, int]] = [(5, 20), (10, 30), (20, 50)]


def _parse_cache_filename(path: Path, symbol: str) -> Optional[Tuple[str, str]]:
    """Parse SYMBOL_YYYYMMDD_YYYYMMDD.pkl cache filenames."""
    stem = path.stem
    prefix = f"{symbol.upper()}_"
    if not stem.upper().startswith(prefix):
        return None

    parts = stem[len(prefix) :].split("_")
    if len(parts) != 2 or not all(len(x) == 8 and x.isdigit() for x in parts):
        return None
    start = f"{parts[0][:4]}-{parts[0][4:6]}-{parts[0][6:]}"
    end = f"{parts[1][:4]}-{parts[1][4:6]}-{parts[1][6:]}"
    return start, end


def _normalize_price_df(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize cached OHLCV data to a sorted, timezone-naive DatetimeIndex."""
    out = df.copy()
    if not isinstance(out.index, pd.DatetimeIndex):
        out.index = pd.to_datetime(out.index)
    if out.index.tz is not None:
        out.index = out.index.tz_localize(None)
    out = out.sort_index()

    required = ["Open", "High", "Low", "Close", "Volume"]
    missing = [c for c in required if c not in out.columns]
    if missing:
        raise ValueError(f"缓存缺少必要列: {missing}")
    return out[required].dropna()


def _slice_df(df: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
    """Slice a normalized DataFrame by inclusive calendar dates."""
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    return df[(df.index >= start) & (df.index <= end)].copy()


def _load_covering_cache(
    *,
    symbol: str,
    start_date: str,
    end_date: str,
    cache_dirs: Sequence[Path],
) -> Tuple[Optional[pd.DataFrame], Optional[Path]]:
    """
    Load the smallest local cache file that fully covers [start_date, end_date].

    The project has both `data/cache` and `data_cache`; this helper treats them as
    read-only cache candidates and chooses the narrowest covering range to avoid
    unnecessary IO while still preventing yfinance rate-limit hits.
    """
    start_key = start_date.replace("-", "")
    end_key = end_date.replace("-", "")
    candidates: List[Tuple[int, Path, str, str]] = []

    for cache_dir in cache_dirs:
        if not cache_dir.exists():
            continue
        for path in cache_dir.rglob(f"{symbol.upper()}_*.pkl"):
            parsed = _parse_cache_filename(path, symbol)
            if parsed is None:
                continue
            cache_start, cache_end = parsed
            cache_start_key = cache_start.replace("-", "")
            cache_end_key = cache_end.replace("-", "")
            if cache_start_key <= start_key and cache_end_key >= end_key:
                span = int(cache_end_key) - int(cache_start_key)
                candidates.append((span, path, cache_start, cache_end))

    for _, path, _, _ in sorted(candidates, key=lambda x: (x[0], x[1].stat().st_size)):
        try:
            with path.open("rb") as f:
                df = pickle.load(f)
            if not isinstance(df, pd.DataFrame):
                continue
            normalized = _normalize_price_df(df)
            sliced = _slice_df(normalized, start_date, end_date)
            if not sliced.empty:
                print(f"[CACHE-COVER] {symbol} {start_date}~{end_date} <- {path}")
                return sliced, path
        except Exception as exc:
            print(f"[WARN] 覆盖缓存读取失败: {path} ({exc})")

    return None, None


def _trading_dates_from_df(df: pd.DataFrame, start_date: str, end_date: str) -> List[str]:
    """Build trading dates from the symbol DataFrame itself."""
    sliced = _slice_df(df, start_date, end_date)
    return [d.strftime("%Y-%m-%d") for d in sliced.index]


def _next_trading_day_from_df(df: pd.DataFrame, current_date: str) -> Optional[str]:
    """Return the next available trading day from the preloaded DataFrame."""
    current = pd.to_datetime(current_date)
    future = df[df.index > current].index
    if len(future) == 0:
        return None
    return future[0].strftime("%Y-%m-%d")


def _to_ts(df: pd.DataFrame, date_str: str) -> pd.Timestamp:
    t = pd.to_datetime(date_str)
    if df.index.tz is not None:
        if t.tzinfo is None:
            t = t.tz_localize(df.index.tz)
        else:
            t = t.tz_convert(df.index.tz)
    return t


def _price_from_df(df: pd.DataFrame, date_str: str, col: str) -> Optional[float]:
    ts = _to_ts(df, date_str)
    if ts not in df.index:
        sub = df[df.index <= ts]
        if sub.empty:
            return None
        ts = sub.index[-1]
    v = df.loc[ts, col]
    try:
        return float(v)
    except Exception:
        return None


def _run_strategy_daily_equity(
    *,
    strategy: Any,
    symbol: str,
    trading_dates: List[str],
    df: pd.DataFrame,
    initial_cash: float,
) -> List[float]:
    """
    Reuse the same semantics as baseline runner:
    - decide at trade_date
    - execute at next trading day open (MKT_OPEN)
    - mark equity at trade_date close
    """
    from tradingagents.core.portfolio_simulator import PortfolioSimulator
    from scripts.runtime.run_signal_export import _validate_signal
    from scripts.experimental.baseline_strategies import StrategyContext

    sim = PortfolioSimulator(symbol=symbol, initial_cash=float(initial_cash))
    equity: List[float] = []

    for day_index, trade_date in enumerate(trading_dates):
        ctx = StrategyContext(
            symbol=symbol,
            trade_date=trade_date,
            df=df,
            day_index=day_index,
            trading_dates=trading_dates,
        )
        raw = strategy.decide(ctx)
        sig = _validate_signal(dict(raw))
        action = str(sig.get("action", "HOLD")).upper()
        target_pct = float(sig.get("target_pct") or 0.0)
        exec_date = _next_trading_day_from_df(df, trade_date)
        if exec_date:
            ep = _price_from_df(df, exec_date, "Open")
            if ep is not None and ep > 0:
                sim.apply_fill(action, target_pct, ep)
                if action == "BUY":
                    sim.set_entry_date_after_buy(exec_date)

        close_px = _price_from_df(df, trade_date, "Close")
        if close_px is None:
            close_px = _price_from_df(df, trade_date, "Open")
        eq = sim.equity_at_price(float(close_px or 0.0))
        equity.append(float(eq))

    return equity


def _ma_label(fast: int, slow: int) -> str:
    """Build a stable CSV column prefix for one MA window."""
    return f"ma_{fast}_{slow}"


def _parse_ma_windows(values: Optional[Sequence[str]]) -> List[Tuple[int, int]]:
    """Parse repeated --ma-window FAST:SLOW values."""
    if not values:
        return list(DEFAULT_MA_WINDOWS)

    windows: List[Tuple[int, int]] = []
    for raw in values:
        token = raw.strip().replace("/", ":").replace(",", ":")
        parts = token.split(":")
        if len(parts) != 2:
            raise ValueError(f"无效 --ma-window: {raw}，格式应为 FAST:SLOW，例如 5:20")
        fast = int(parts[0])
        slow = int(parts[1])
        if fast <= 0 or slow <= 0 or fast >= slow:
            raise ValueError(f"无效 --ma-window: {raw}，要求 0 < FAST < SLOW")
        windows.append((fast, slow))
    return windows


def _base_row(
    *,
    date: str,
    segment: str,
    close_price: Optional[float],
    bh_eq: float,
    bh_cum: float,
    bh_day: float,
) -> Dict[str, Any]:
    """Build invariant row fields before strategy-specific columns are added."""
    return {
        "date": date,
        "segment": segment,
        "close_price": close_price if close_price is not None else "",
        "bh_equity": bh_eq,
        "bh_cumulative_return": bh_cum,
        "bh_daily_return": bh_day,
    }


def export_segments_csv(
    *,
    symbol: str,
    initial_cash: float,
    ma_windows: Sequence[Tuple[int, int]],
    macd_fast: int,
    macd_slow: int,
    macd_signal: int,
    use_proxy: bool,
    proxy_host: Optional[str],
    proxy_port: Optional[int],
    proxy_type: Optional[str],
    cache_dirs: Sequence[Path],
    no_download: bool,
    output_csv: Path,
) -> Path:
    if use_proxy:
        setup_proxy(proxy_host, proxy_port, proxy_type)

    data_adapter = DataAdapter(use_cache=True)
    all_rows: List[Dict[str, Any]] = []
    max_ma_slow = max((slow for _, slow in ma_windows), default=60)

    for seg_name, start_date, end_date in SEGMENTS:
        # Warm start: allow indicators to be computed without forward-looking.
        warm_start = (
            # Keep enough pre-segment bars for the slowest MA without forward-looking.
            datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=max(120, max_ma_slow * 2))
        ).strftime("%Y-%m-%d")
        # Include a small execution buffer so the last signal can find the next open if cached.
        load_end = (datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=10)).strftime("%Y-%m-%d")

        df, cache_path = _load_covering_cache(
            symbol=symbol,
            start_date=warm_start,
            end_date=load_end,
            cache_dirs=cache_dirs,
        )
        if df is None and not no_download:
            df = data_adapter.load_stock_data_until(symbol, load_end, start_date=warm_start)
            cache_path = None
        if df is None or len(df) == 0:
            print(f"[WARN] segment={seg_name} 数据为空，跳过（缓存不覆盖且下载失败/禁用）")
            continue
        df = _normalize_price_df(df)

        trading_dates = _trading_dates_from_df(df, start_date, end_date)
        if not trading_dates:
            print(f"[WARN] segment={seg_name} 没有目标区间交易日，跳过")
            continue

        df_macd = add_macd_columns(df, fast=macd_fast, slow=macd_slow, signal=macd_signal)
        df_kdj = add_kdj_columns(df)

        reference_ma_fast, reference_ma_slow = ma_windows[0] if ma_windows else (5, 20)
        bh = build_strategy("bh", reference_ma_fast, reference_ma_slow, macd_fast, macd_slow, macd_signal)
        macd = build_strategy("macd", reference_ma_fast, reference_ma_slow, macd_fast, macd_slow, macd_signal)
        kdj = build_strategy("kdj", reference_ma_fast, reference_ma_slow, macd_fast, macd_slow, macd_signal)

        bh_eq = _run_strategy_daily_equity(
            strategy=bh,
            symbol=symbol,
            trading_dates=trading_dates,
            df=df,
            initial_cash=initial_cash,
        )
        macd_eq = _run_strategy_daily_equity(
            strategy=macd,
            symbol=symbol,
            trading_dates=trading_dates,
            df=df_macd,
            initial_cash=initial_cash,
        )
        kdj_eq = _run_strategy_daily_equity(
            strategy=kdj,
            symbol=symbol,
            trading_dates=trading_dates,
            df=df_kdj,
            initial_cash=initial_cash,
        )

        bh_day = compute_daily_returns(bh_eq)
        macd_day = compute_daily_returns(macd_eq)
        kdj_day = compute_daily_returns(kdj_eq)

        bh_cum = compute_cumulative_returns(bh_eq, initial_cash)
        macd_cum = compute_cumulative_returns(macd_eq, initial_cash)
        kdj_cum = compute_cumulative_returns(kdj_eq, initial_cash)

        ma_payloads: List[Tuple[str, List[float], List[float], List[float]]] = []
        for fast, slow in ma_windows:
            label = _ma_label(fast, slow)
            df_ma = add_ma_columns(df, fast=fast, slow=slow)
            ma = build_strategy("ma", fast, slow, macd_fast, macd_slow, macd_signal)
            ma_eq = _run_strategy_daily_equity(
                strategy=ma,
                symbol=symbol,
                trading_dates=trading_dates,
                df=df_ma,
                initial_cash=initial_cash,
            )
            ma_payloads.append(
                (
                    label,
                    ma_eq,
                    compute_cumulative_returns(ma_eq, initial_cash),
                    compute_daily_returns(ma_eq),
                )
            )

        # close price aligned to trade dates (from preloaded df; fallback to Open)
        closes: List[Optional[float]] = []
        for d in trading_dates:
            cp = _price_from_df(df, d, "Close")
            if cp is None:
                cp = _price_from_df(df, d, "Open")
            closes.append(cp)

        for i, d in enumerate(trading_dates):
            row = _base_row(
                date=d,
                segment=seg_name,
                close_price=closes[i],
                bh_eq=float(bh_eq[i]),
                bh_cum=float(bh_cum[i]),
                bh_day=float(bh_day[i]),
            )
            for label, eqs, cums, days in ma_payloads:
                row[f"{label}_equity"] = float(eqs[i])
                row[f"{label}_cumulative_return"] = float(cums[i])
                row[f"{label}_daily_return"] = float(days[i])
            row["macd_equity"] = float(macd_eq[i])
            row["macd_cumulative_return"] = float(macd_cum[i])
            row["macd_daily_return"] = float(macd_day[i])
            row["kdj_equity"] = float(kdj_eq[i])
            row["kdj_cumulative_return"] = float(kdj_cum[i])
            row["kdj_daily_return"] = float(kdj_day[i])
            row["data_source"] = str(cache_path) if cache_path else "download_or_exact_cache"
            all_rows.append(row)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    ma_columns = [
        col
        for fast, slow in ma_windows
        for col in (
            f"{_ma_label(fast, slow)}_equity",
            f"{_ma_label(fast, slow)}_cumulative_return",
            f"{_ma_label(fast, slow)}_daily_return",
        )
    ]
    columns = [
        "date",
        "segment",
        "close_price",
        "bh_equity",
        "bh_cumulative_return",
        "bh_daily_return",
        *ma_columns,
        "macd_equity",
        "macd_cumulative_return",
        "macd_daily_return",
        "kdj_equity",
        "kdj_cumulative_return",
        "kdj_daily_return",
        "data_source",
    ]
    out_df = pd.DataFrame(all_rows, columns=columns)
    if out_df.empty:
        raise RuntimeError(
            "未生成任何行：三段区间都没有拉到数据。"
            "请稍后重试/开启代理/预先下载数据到缓存后再跑。"
        )
    out_df.to_csv(output_csv, index=False, encoding="gbk")
    return output_csv


def plot_segments_csv(csv_path: Path, plot_path: Path, symbol: str) -> Path:
    """Plot segment-level cumulative returns from the exported GBK CSV."""
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    df = pd.read_csv(csv_path, encoding="gbk")
    if df.empty:
        raise RuntimeError(f"CSV 为空，无法绘图: {csv_path}")

    return_cols = [
        c
        for c in df.columns
        if c.endswith("_cumulative_return") and c not in {"close_price"}
    ]
    if not return_cols:
        raise RuntimeError("CSV 中没有 cumulative_return 列，无法绘图")

    label_by_col = {
        "bh_cumulative_return": "BH",
        "macd_cumulative_return": "MACD 12/26/9",
        "kdj_cumulative_return": "KDJ 9/3/3",
    }
    for c in return_cols:
        if c.startswith("ma_"):
            parts = c.removesuffix("_cumulative_return").split("_")
            if len(parts) == 3:
                label_by_col[c] = f"MA {parts[1]}/{parts[2]}"

    segments = list(dict.fromkeys(df["segment"].astype(str).tolist()))
    fig, axes = plt.subplots(len(segments), 1, figsize=(13, 4.2 * len(segments)), sharex=False)
    if len(segments) == 1:
        axes = [axes]

    for ax, segment in zip(axes, segments):
        sub = df[df["segment"] == segment].copy()
        sub["date"] = pd.to_datetime(sub["date"])
        for col in return_cols:
            ax.plot(
                sub["date"],
                sub[col].astype(float) * 100.0,
                linewidth=1.8,
                label=label_by_col.get(col, col.removesuffix("_cumulative_return")),
            )
        ax.axhline(0, color="#888888", linewidth=0.8, alpha=0.7)
        ax.set_title(segment, loc="left", fontsize=11)
        ax.set_ylabel("Cumulative Return (%)")
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best", fontsize=9)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))

    fig.suptitle(f"{symbol} Baseline Strategy Daily Performance", fontsize=14, y=0.995)
    fig.autofmt_xdate()
    fig.tight_layout()
    plot_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)
    return plot_path


def main() -> None:
    p = argparse.ArgumentParser(description="Export baseline daily performance for 3 fixed segments (GBK CSV).")
    p.add_argument("--symbol", type=str, default="NVDA")
    p.add_argument("--initial-cash", type=float, default=100_000.0)
    p.add_argument(
        "--ma-window",
        action="append",
        default=None,
        help="MA 参数窗口，格式 FAST:SLOW，可重复传入；默认 5:20、10:30、20:50。",
    )
    p.add_argument("--macd-fast", type=int, default=12)
    p.add_argument("--macd-slow", type=int, default=26)
    p.add_argument("--macd-signal", type=int, default=9)
    p.add_argument("--use-proxy", action="store_true", default=False)
    p.add_argument("--proxy-host", type=str, default=None)
    p.add_argument("--proxy-port", type=int, default=None)
    p.add_argument("--proxy-type", type=str, default=None)
    p.add_argument(
        "--cache-dir",
        action="append",
        default=None,
        help="本地缓存目录，可重复传入；默认依次查 data/cache 与 data_cache。",
    )
    p.add_argument(
        "--no-download",
        action="store_true",
        default=False,
        help="只使用本地覆盖缓存，不再尝试 yfinance 下载。",
    )
    p.add_argument("--output-csv", type=str, default=None)
    p.add_argument("--plot-png", type=str, default=None)
    p.add_argument("--no-plot", action="store_true", default=False)
    args = p.parse_args()

    ts = time.strftime("%Y%m%d_%H%M%S")
    out = (
        Path(args.output_csv)
        if args.output_csv
        else (REPO_ROOT / "storage" / "baseline_backtests" / f"baseline_segments_{args.symbol}_{ts}.csv")
    )

    path = export_segments_csv(
        symbol=args.symbol,
        initial_cash=float(args.initial_cash),
        ma_windows=_parse_ma_windows(args.ma_window),
        macd_fast=int(args.macd_fast),
        macd_slow=int(args.macd_slow),
        macd_signal=int(args.macd_signal),
        use_proxy=bool(args.use_proxy),
        proxy_host=args.proxy_host,
        proxy_port=args.proxy_port,
        proxy_type=args.proxy_type,
        cache_dirs=(
            [Path(x) for x in args.cache_dir]
            if args.cache_dir
            else [REPO_ROOT / "data" / "cache", REPO_ROOT / "data_cache"]
        ),
        no_download=bool(args.no_download),
        output_csv=out,
    )
    print(f"[OK] Wrote GBK CSV: {path.resolve()}")
    if not args.no_plot:
        plot_path = Path(args.plot_png) if args.plot_png else path.with_name(f"{path.stem}_cumulative_returns.png")
        plotted = plot_segments_csv(path, plot_path, args.symbol)
        print(f"[OK] Wrote plot PNG: {plotted.resolve()}")


if __name__ == "__main__":
    main()

