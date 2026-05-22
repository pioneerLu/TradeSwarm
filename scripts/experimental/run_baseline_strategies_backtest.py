#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基准策略（BH / MA / MACD）对比回测：与 DataAdapter + PortfolioSimulator + 下一交易日开盘成交语义对齐。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.experimental.baseline_metrics import (  # noqa: E402
    compute_metrics,
    write_equity_csv,
)
from scripts.experimental.baseline_strategies import (  # noqa: E402
    StrategyContext,
    add_ma_columns,
    add_macd_columns,
    add_kdj_columns,
    build_strategy,
)
from scripts.runtime.run_signal_export import _validate_signal, get_trading_dates  # noqa: E402
from tradingagents.core.data.loader import setup_proxy  # noqa: E402
from tradingagents.core.data_adapter import DataAdapter  # noqa: E402
from tradingagents.core.portfolio_simulator import PortfolioSimulator  # noqa: E402


def _to_ts(df, date_str: str):
    t = pd.to_datetime(date_str)
    if df.index.tz is not None:
        if t.tzinfo is None:
            t = t.tz_localize(df.index.tz)
        else:
            t = t.tz_convert(df.index.tz)
    return t


def _price_from_df(df, date_str: str, col: str) -> Optional[float]:
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


def _run_one_strategy(
    *,
    strategy: Any,
    symbol: str,
    trading_dates: List[str],
    df: Any,
    data_adapter: DataAdapter,
    initial_cash: float,
) -> Tuple[Dict[str, Any], List[Tuple[str, Dict[str, Any]]], List[Dict[str, Any]]]:
    """返回 {metrics, daily}、signals 列表、(execution_date, payload)、已平仓交易记录。"""
    sim = PortfolioSimulator(symbol=symbol, initial_cash=initial_cash)
    daily_equity: List[float] = []
    daily_dates: List[str] = []
    daily_rows: List[Dict[str, Any]] = []
    signals_for_export: List[Tuple[str, Dict[str, Any]]] = []
    closed_trades: List[Dict[str, Any]] = []
    pending_entry: Optional[Tuple[str, float]] = None  # (buy_exec_date, buy_open)

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
        exec_date = data_adapter.get_next_trading_day(trade_date, symbol=symbol)

        full_sig: Dict[str, Any] = {
            "action": action,
            "target_pct": target_pct if action != "SELL" else 0.0,
            "stop_loss": None,
            "take_profit": None,
            "entry_type": str(sig.get("entry_type", "MKT_OPEN")).upper(),
            "entry_price": None,
            "reason": str(raw.get("reason", "")),
            "is_exploratory": False,
            "execution_date": exec_date,
            "date": trade_date,
            "symbol": symbol,
        }
        if exec_date:
            ep = _price_from_df(df, exec_date, "Open")
            if ep is not None and ep > 0:
                had_shares = sim.shares > 1e-9
                sim.apply_fill(action, float(sig.get("target_pct") or 0.0), ep)
                if action == "BUY" and not had_shares:
                    sim.set_entry_date_after_buy(exec_date)
                    pending_entry = (exec_date, ep)
                elif action == "SELL" and had_shares and pending_entry is not None:
                    buy_d, buy_p = pending_entry
                    pnl_pct = (ep - buy_p) / buy_p if buy_p > 0 else 0.0
                    hd = (_parse_day(exec_date) - _parse_day(buy_d)).days
                    closed_trades.append(
                        {
                            "pnl_pct": float(pnl_pct),
                            "holding_days": float(hd),
                            "buy_exec_date": buy_d,
                            "sell_exec_date": exec_date,
                        }
                    )
                    pending_entry = None
                elif action == "BUY" and had_shares:
                    # 加仓：简化处理——重置入场参考价为最近一次 BUY 开盘价
                    pending_entry = (exec_date, ep)

            signals_for_export.append(
                (
                    exec_date,
                    {
                        "action": full_sig["action"],
                        "target_pct": full_sig["target_pct"],
                        "stop_loss": None,
                        "take_profit": None,
                        "entry_type": full_sig["entry_type"],
                        "entry_price": None,
                        "reason": full_sig["reason"],
                        "is_exploratory": False,
                        "execution_date": exec_date,
                        "date": trade_date,
                        "symbol": symbol,
                    },
                )
            )

        close_px = _price_from_df(df, trade_date, "Close")
        if close_px is None:
            close_px = _price_from_df(df, trade_date, "Open")
        eq = sim.equity_at_price(close_px if close_px else 0.0)

        daily_equity.append(eq)
        daily_dates.append(trade_date)
        daily_rows.append(
            {
                "trade_date": trade_date,
                "action": action,
                "execution_date": exec_date,
                "close": close_px,
                "equity_close": eq,
                "shares": float(sim.shares),
                "cash": float(sim.cash),
            }
        )

    metrics = compute_metrics(
        daily_equity=daily_equity,
        daily_dates=daily_dates,
        initial_cash=initial_cash,
        closed_trades=closed_trades,
        first_date=trading_dates[0],
        last_date=trading_dates[-1],
    )
    return (
        {"metrics": metrics, "daily": daily_rows},
        list(signals_for_export),
        closed_trades,
    )


def _parse_day(s: str) -> datetime:
    return datetime.strptime(s[:10], "%Y-%m-%d")


def _load_compare_interleaved(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    fps = data.get("final_portfolio_state") or {}
    tr = fps.get("total_return")
    return {
        "agent_total_return_pct": tr,
        "agent_source_file": str(path.resolve()),
        "agent_final_equity": fps.get("total_value"),
    }


def _plot_equity_curves(
    out_png: Path,
    symbol: str,
    df: Any,
    trading_dates: List[str],
    strategies_payload: Dict[str, Any],
) -> None:
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    fig, ax1 = plt.subplots(figsize=(12, 6))
    dates = [datetime.strptime(d, "%Y-%m-%d") for d in trading_dates]
    close_series = [_price_from_df(df, d, "Close") for d in trading_dates]
    c0 = close_series[0] or 1.0
    norm_px = [((c or c0) / c0) * 100.0 for c in close_series]
    ax1.plot(dates, norm_px, label=f"{symbol} Close (norm=100)", color="gray", linewidth=1.2, alpha=0.85)

    ax2 = ax1.twinx()
    for key, block in strategies_payload.items():
        m = block.get("metrics") or {}
        daily = block.get("daily") or []
        eq = [row.get("equity_close") for row in daily]
        if not eq:
            continue
        e0 = eq[0] or 1.0
        neq = [(e / e0) * 100.0 for e in eq]
        ax2.plot(dates[: len(neq)], neq, label=key.upper(), linewidth=1.5)

    ax1.set_xlabel("Date")
    ax1.set_ylabel(f"{symbol} price (index 100)")
    ax2.set_ylabel("Equity (index 100)")
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    fig.autofmt_xdate()
    ax1.legend(loc="upper left")
    ax2.legend(loc="upper right")
    plt.title(f"Baseline strategies vs {symbol} — equity curves")
    plt.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_png, dpi=120)
    plt.close()


def _apply_yfinance_proxy(
    *,
    use_proxy: bool,
    proxy_host: Optional[str],
    proxy_port: Optional[int],
    proxy_type: Optional[str],
) -> bool:
    """
    yfinance 经 tradingagents.core.data.loader.load_stock_data 拉数；
    与导出脚本一致：USE_PROXY + PROXY_HOST/PROXY_PORT/PROXY_TYPE，并调用 setup_proxy 写入 HTTP(S)_PROXY。
    若已在环境中设置 HTTP_PROXY/HTTPS_PROXY，可不传 --use-proxy（urllib 仍会走代理）。
    """
    if proxy_host:
        os.environ["PROXY_HOST"] = proxy_host
    if proxy_port is not None:
        os.environ["PROXY_PORT"] = str(proxy_port)
    if proxy_type:
        os.environ["PROXY_TYPE"] = proxy_type
    if use_proxy:
        os.environ["USE_PROXY"] = "true"
        ph = os.getenv("PROXY_HOST")
        pp = os.getenv("PROXY_PORT")
        if not ph or not pp:
            print(
                "[ERROR] --use-proxy 需要设置 PROXY_HOST 与 PROXY_PORT（环境变量或 --proxy-host/--proxy-port）"
            )
            return False
        setup_proxy()
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Baseline MA / MACD / KDJ / BH backtest (PortfolioSimulator).")
    parser.add_argument("--symbol", type=str, default="NVDA")
    parser.add_argument("--start", type=str, required=True)
    parser.add_argument("--end", type=str, required=True)
    parser.add_argument("--initial-cash", type=float, default=100_000.0)
    parser.add_argument("--strategies", type=str, default="bh,ma,macd")
    parser.add_argument("--ma-fast", type=int, default=10)
    parser.add_argument("--ma-slow", type=int, default=50)
    parser.add_argument("--macd-fast", type=int, default=12)
    parser.add_argument("--macd-slow", type=int, default=26)
    parser.add_argument("--macd-signal", type=int, default=9)
    parser.add_argument("--kdj-n", type=int, default=9)
    parser.add_argument("--kdj-k-smooth", type=int, default=3)
    parser.add_argument("--kdj-d-smooth", type=int, default=3)
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument("--no-plot", action="store_true")
    parser.add_argument(
        "--export-csv-dir",
        type=str,
        default=None,
        help="导出每个策略的每日序列 CSV（默认与输出 JSON 同目录）",
    )
    parser.add_argument("--export-signals-dir", type=str, default=None)
    parser.add_argument("--compare-interleaved-json", type=str, default=None)
    parser.add_argument(
        "--use-proxy",
        action="store_true",
        help="启用代理拉取 yfinance 数据（需 PROXY_HOST/PROXY_PORT 或下方参数）",
    )
    parser.add_argument("--proxy-host", type=str, default=None, help="覆盖环境变量 PROXY_HOST")
    parser.add_argument("--proxy-port", type=int, default=None, help="覆盖环境变量 PROXY_PORT")
    parser.add_argument("--proxy-type", type=str, default=None, help="http 或 socks5，默认环境变量 PROXY_TYPE 或 http")
    args = parser.parse_args()

    if not _apply_yfinance_proxy(
        use_proxy=args.use_proxy,
        proxy_host=args.proxy_host,
        proxy_port=args.proxy_port,
        proxy_type=args.proxy_type,
    ):
        return 1

    data_adapter = DataAdapter(use_cache=True)
    warm_start = (_parse_day(args.start) - timedelta(days=130)).strftime("%Y-%m-%d")
    raw_df = data_adapter.load_stock_data_until(args.symbol, args.end, start_date=warm_start)
    if raw_df is None or len(raw_df) == 0:
        print(f"[ERROR] 无法加载 {args.symbol} 行情")
        return 1

    df = add_ma_columns(raw_df, args.ma_fast, args.ma_slow)
    df = add_macd_columns(df, args.macd_fast, args.macd_slow, args.macd_signal)
    df = add_kdj_columns(df, n=int(args.kdj_n), k_smooth=int(args.kdj_k_smooth), d_smooth=int(args.kdj_d_smooth))

    trading_dates = get_trading_dates(args.start, args.end, data_adapter)
    trading_dates = [d for d in trading_dates if _price_from_df(df, d, "Close") is not None]
    if not trading_dates:
        print("[ERROR] 区间内无有效交易日数据")
        return 1

    names = [x.strip().lower() for x in args.strategies.split(",") if x.strip()]
    strategies_out: Dict[str, Any] = {}
    export_by_name: Dict[str, Dict[str, Any]] = {}

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_out = REPO_ROOT / "storage" / "baseline_backtests" / f"baseline_{args.symbol}_{ts}.json"

    for n in names:
        strat = build_strategy(
            n,
            args.ma_fast,
            args.ma_slow,
            args.macd_fast,
            args.macd_slow,
            args.macd_signal,
            kdj_n=int(args.kdj_n),
            kdj_k_smooth=int(args.kdj_k_smooth),
            kdj_d_smooth=int(args.kdj_d_smooth),
        )
        block, sig_list, _closed = _run_one_strategy(
            strategy=strat,
            symbol=args.symbol,
            trading_dates=trading_dates,
            df=df,
            data_adapter=data_adapter,
            initial_cash=args.initial_cash,
        )
        strategies_out[strat.name] = block
        by_exec: Dict[str, Any] = {}
        for ed, pl in sig_list:
            if ed:
                by_exec[ed] = pl
        export_by_name[strat.name] = {
            "symbol": args.symbol,
            "start_date": args.start,
            "end_date": args.end,
            "export_mode": "backtest",
            "experiment_id": f"baseline_{strat.name}",
            "enabled_analysts": [],
            "by_execution_date": by_exec,
        }

    payload: Dict[str, Any] = {
        "symbol": args.symbol,
        "start_date": args.start,
        "end_date": args.end,
        "initial_cash": args.initial_cash,
        "params": {
            "ma_fast": args.ma_fast,
            "ma_slow": args.ma_slow,
            "macd": [args.macd_fast, args.macd_slow, args.macd_signal],
            "kdj": [int(args.kdj_n), int(args.kdj_k_smooth), int(args.kdj_d_smooth)],
        },
        "strategies": strategies_out,
    }

    if args.compare_interleaved_json:
        p = Path(args.compare_interleaved_json)
        if p.is_file():
            payload["compare"] = _load_compare_interleaved(p)
        else:
            print(f"[WARN] compare 文件不存在: {p}")

    out_path = Path(args.output) if args.output else default_out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] 已写入 {out_path.resolve()}")

    csv_dir = Path(args.export_csv_dir) if args.export_csv_dir else out_path.parent
    csv_dir.mkdir(parents=True, exist_ok=True)
    for name, block in strategies_out.items():
        daily = block.get("daily") or []
        dates = [str(r.get("trade_date")) for r in daily]
        equity = [float(r.get("equity_close") or 0.0) for r in daily]
        close_prices = []
        for r in daily:
            c = r.get("close")
            try:
                close_prices.append(float(c) if c is not None else None)
            except Exception:
                close_prices.append(None)
        csv_path = csv_dir / f"{out_path.stem}_{name}.csv"
        write_equity_csv(
            csv_path,
            dates=dates,
            equity=equity,
            initial_cash=float(args.initial_cash),
            close_prices=close_prices,
        )
        print(f"[OK] CSV -> {csv_path.resolve()}")

    if args.export_signals_dir:
        exdir = Path(args.export_signals_dir)
        exdir.mkdir(parents=True, exist_ok=True)
        for name, sig_payload in export_by_name.items():
            fp = exdir / f"signals_{name}.json"
            fp.write_text(json.dumps(sig_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[OK] signals -> {fp.resolve()}")

    if not args.no_plot:
        plot_path = out_path.with_name(out_path.stem + "_equity_curves.png")
        try:
            _plot_equity_curves(plot_path, args.symbol, df, trading_dates, strategies_out)
            print(f"[OK] 图表 -> {plot_path.resolve()}")
        except Exception as e:
            print(f"[WARN] 绘图失败（可 pip install matplotlib）: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
