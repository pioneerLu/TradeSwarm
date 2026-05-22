#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Generate interleaved backtest charts in a separate process.

This isolates matplotlib/OpenMP issues (e.g. libiomp5md.dll conflicts) from the
main interleaved backtest orchestrator so core JSON/CSV artifacts are not lost.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional


def _parse_dates(dates: List[str]):
    out = []
    for d in dates:
        try:
            out.append(datetime.strptime(d, "%Y-%m-%d").date())
        except Exception:
            out.append(d)
    return out


def _plot_performance_chart(
    *,
    symbol: str,
    trading_dates: List[str],
    aligned_equity: List[float],
    close_prices: List[Optional[float]],
    initial_cash: float,
    output_path: Path,
) -> None:
    import matplotlib.pyplot as plt

    x_dates = _parse_dates(trading_dates)
    strategy_ret_pct = [((float(e) / float(initial_cash)) - 1.0) * 100.0 for e in aligned_equity]

    aligned_close: List[float] = []
    last_close: Optional[float] = None
    for c in close_prices:
        if c is not None and c > 0:
            last_close = float(c)
        aligned_close.append(last_close if last_close is not None else 0.0)
    first_close = next((c for c in aligned_close if c > 0), None)
    if first_close is None:
        price_ret_pct = [0.0 for _ in aligned_close]
    else:
        price_ret_pct = [((c / first_close) - 1.0) * 100.0 if c > 0 else 0.0 for c in aligned_close]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(11, 4.5))
    plt.plot(x_dates, strategy_ret_pct, label="Strategy Return %", linewidth=2.0)
    plt.plot(x_dates, price_ret_pct, label=f"{symbol} Price Change %", linewidth=1.8, alpha=0.9)
    plt.axhline(0, color="gray", linewidth=1.0, alpha=0.5)
    plt.xlabel("Date")
    plt.ylabel("Change (%)")
    plt.title(f"Interleaved Backtest: Strategy vs {symbol} Price")
    plt.legend()
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def _plot_equity_curve(
    *,
    trading_dates: List[str],
    aligned_equity: List[float],
    initial_cash: float,
    output_path: Path,
    title: str,
) -> None:
    import matplotlib.pyplot as plt

    x_dates = _parse_dates(trading_dates)
    cum_ret_pct = [((float(e) / float(initial_cash)) - 1.0) * 100.0 for e in aligned_equity]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(11, 4.5))
    plt.plot(x_dates, cum_ret_pct, label="Cumulative Return %", linewidth=2.0)
    plt.axhline(0, color="gray", linewidth=1.0, alpha=0.5)
    plt.xlabel("Date")
    plt.ylabel("Cumulative Return (%)")
    plt.title(title)
    plt.legend()
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot interleaved charts from a result json.")
    parser.add_argument("--input-json", type=str, required=True)
    parser.add_argument("--out-dir", type=str, required=True)
    args = parser.parse_args()

    in_path = Path(args.input_json)
    out_dir = Path(args.out_dir)
    payload = json.loads(in_path.read_text(encoding="utf-8"))

    symbol = payload.get("symbol") or "SYMBOL"
    trading_dates = payload.get("daily_dates") or []
    aligned_equity = payload.get("daily_equity") or []
    initial_cash = float(payload.get("initial_cash") or 100000.0)

    # close_prices might not be persisted; fall back to empty (price line becomes 0)
    close_prices = payload.get("close_prices") or []
    close_prices = close_prices if isinstance(close_prices, list) else []

    ts = in_path.stem.replace("interleaved_", "")
    perf_png = out_dir / f"interleaved_{ts}_return_vs_price.png"
    eq_png = out_dir / f"interleaved_{ts}_equity_curve.png"

    _plot_performance_chart(
        symbol=str(symbol),
        trading_dates=list(trading_dates),
        aligned_equity=list(aligned_equity),
        close_prices=[(float(x) if x is not None else None) for x in close_prices],
        initial_cash=float(initial_cash),
        output_path=perf_png,
    )
    _plot_equity_curve(
        trading_dates=list(trading_dates),
        aligned_equity=list(aligned_equity),
        initial_cash=float(initial_cash),
        output_path=eq_png,
        title=f"Interleaved Backtest: {symbol} Cumulative Return",
    )


if __name__ == "__main__":
    main()

