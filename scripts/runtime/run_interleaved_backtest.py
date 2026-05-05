#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Interleaved Agent-QC backtest orchestrator.

For each trading day:
  1. Load real portfolio state from previous QC run (or empty on day 1).
  2. Run the agent graph for that day, producing a signal.
  3. Accumulate signal into signals.json.
  4. Sync files to lean_workspace and run lean backtest.
  5. Parse the QC daily snapshot (Object Store) to get real execution results.
  6. Persist the snapshot to memory.db.
  7. Feed the real portfolio state into the next day's agent.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.experimental.baseline_metrics import (  # noqa: E402
    compute_metrics,
)
from scripts.runtime.run_signal_export import (  # noqa: E402
    _get_runtime_dependencies,
    _apply_strategy_skills_env,
    _normalize_enabled_analysts,
    _derive_experiment_id,
    _validate_signal,
    get_trading_dates,
    run_single_day,
)
from tradingagents.config import get_llm_metadata, get_strategy_skills_config  # noqa: E402
from tradingagents.agents.utils.hybrid_memory import create_hybrid_trading_memory  # noqa: E402
from tradingagents.core.lean_result_parser import (  # noqa: E402
    parse_daily_snapshot,
    parse_latest_snapshot,
    snapshot_to_agent_fields,
)


DEFAULT_LEAN_WORKSPACE = REPO_ROOT / "lean_workspace"
DEFAULT_LEAN_PROJECT = "TradeSwarm"


def _read_close_prices_from_lean_custom_csv(
    *,
    trading_dates: List[str],
    lean_workspace: Path,
    symbol: str,
) -> List[Optional[float]]:
    """
    直接从 Lean custom CSV 读取 close（避免在 metrics 阶段触发 yfinance 下载）。
    CSV 列：date,open,high,low,close,volume
    """
    csv_path = _lean_custom_csv_path(lean_workspace, symbol)
    if not csv_path.exists():
        return [None for _ in trading_dates]
    by_date: Dict[str, Optional[float]] = {}
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                d = (row.get("date") or "").strip()
                if not d:
                    continue
                raw = row.get("close")
                try:
                    v = float(raw) if raw is not None and str(raw).strip() != "" else None
                except Exception:
                    v = None
                if v is not None and v > 0:
                    by_date[d] = v
    except Exception:
        return [None for _ in trading_dates]

    out: List[Optional[float]] = []
    last: Optional[float] = None
    for d in trading_dates:
        v = by_date.get(d)
        if v is not None and v > 0:
            last = v
        out.append(last)
    return out


def _write_interleaved_observability_csv(
    *,
    path: Path,
    results: List[Dict[str, Any]],
    trading_dates: List[str],
    aligned_equity: List[float],
    initial_cash: float,
    close_prices: List[Optional[float]],
    daily_returns: List[float],
    cumulative_returns: List[float],
) -> None:
    """
    写 interleaved 专用 CSV：
    - 前 5 列与基线一致：date,equity,cumulative_return,daily_return,close_price
    - 后续追加可观测字段，便于复盘挂单/成交与信号参数。
    """
    by_date = {str(r.get("trade_date")): r for r in results}
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "date",
            "equity",
            "cumulative_return",
            "daily_return",
            "close_price",
            "signal_action",
            "execution_date",
            "shares",
            "target_pct",
            "entry_type",
            "market_regime",
            "selected_skill",
            "regime_confidence",
            "regime_evidence",
            "skill_router_mode",
            "forced_selected_skill",
            "reflection_market_regime",
            "reflection_selected_skill",
            "reflection_confidence",
            "reflection_evidence",
            "limit_price",
            "cancel_pending_orders",
            "pending_orders_count",
            "pending_order_limits",
            "filled_today_count",
            "last_fill_offset_days",
        ]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for i, d in enumerate(trading_dates):
            r = by_date.get(d, {})
            cp = close_prices[i] if i < len(close_prices) else None
            w.writerow(
                {
                    "date": d,
                    "equity": float(aligned_equity[i]) if i < len(aligned_equity) else "",
                    "cumulative_return": float(cumulative_returns[i]) if i < len(cumulative_returns) else 0.0,
                    "daily_return": float(daily_returns[i]) if i < len(daily_returns) else 0.0,
                    "close_price": float(cp) if cp is not None else "",
                    "signal_action": r.get("signal_action"),
                    "execution_date": r.get("execution_date"),
                    "shares": r.get("shares"),
                    "target_pct": r.get("target_pct"),
                    "entry_type": r.get("entry_type"),
                    "market_regime": r.get("market_regime"),
                    "selected_skill": r.get("selected_skill"),
                    "regime_confidence": r.get("regime_confidence"),
                    "regime_evidence": json.dumps(r.get("regime_evidence") or [], ensure_ascii=False),
                    "skill_router_mode": r.get("skill_router_mode"),
                    "forced_selected_skill": r.get("forced_selected_skill"),
                    "reflection_market_regime": r.get("reflection_market_regime"),
                    "reflection_selected_skill": r.get("reflection_selected_skill"),
                    "reflection_confidence": r.get("reflection_confidence"),
                    "reflection_evidence": json.dumps(r.get("reflection_evidence") or [], ensure_ascii=False),
                    "limit_price": r.get("limit_price"),
                    "cancel_pending_orders": r.get("cancel_pending_orders"),
                    "pending_orders_count": r.get("pending_orders_count"),
                    "pending_order_limits": json.dumps(r.get("pending_order_limits") or [], ensure_ascii=False),
                    "filled_today_count": r.get("filled_today_count"),
                    "last_fill_offset_days": r.get("last_fill_offset_days"),
                }
            )

def _align_equity_series(
    *,
    trading_dates: List[str],
    daily_results: List[Dict[str, Any]],
    initial_cash: float,
) -> List[float]:
    """按 trading_dates 对齐 equity（daily_results 可能缺天/None），用前值填充。"""
    equity_by_date = {str(item.get("trade_date")): item.get("equity") for item in daily_results}
    aligned: List[float] = []
    last_equity = float(initial_cash)
    for d in trading_dates:
        e = equity_by_date.get(d)
        if e is not None:
            try:
                last_equity = float(e)
            except Exception:
                pass
        aligned.append(last_equity)
    return aligned


def _infer_closed_trades_from_shares(
    *,
    daily_results: List[Dict[str, Any]],
    close_prices: List[Optional[float]],
) -> List[Dict[str, Any]]:
    """
    从 shares 的 0->>0 / >>0->0 变更推导已平仓交易。
    用 close_prices 估算收益（pnl_pct）与持仓天数（calendar days）。
    """
    def _dt(s: str) -> datetime:
        return datetime.strptime(s[:10], "%Y-%m-%d")

    closed: List[Dict[str, Any]] = []
    entry_idx: Optional[int] = None
    entry_date: Optional[str] = None
    entry_px: Optional[float] = None

    for i, row in enumerate(daily_results):
        d = str(row.get("trade_date") or "")
        if not d:
            continue
        sh_raw = row.get("shares")
        try:
            sh = float(sh_raw) if sh_raw is not None else 0.0
        except Exception:
            sh = 0.0

        px = close_prices[i] if i < len(close_prices) else None

        if entry_idx is None:
            if sh > 1e-9:
                # 开仓
                entry_idx = i
                entry_date = d
                entry_px = float(px) if px is not None and px > 0 else None
        else:
            if sh <= 1e-9:
                # 平仓
                exit_date = d
                exit_px = float(px) if px is not None and px > 0 else None
                if entry_px is not None and exit_px is not None and entry_px > 0:
                    pnl_pct = (exit_px - entry_px) / entry_px
                else:
                    pnl_pct = 0.0
                try:
                    hd = (_dt(exit_date) - _dt(entry_date or exit_date)).days
                except Exception:
                    hd = 0
                closed.append(
                    {
                        "pnl_pct": float(pnl_pct),
                        "holding_days": float(hd),
                        "buy_trade_date": entry_date,
                        "sell_trade_date": exit_date,
                    }
                )
                entry_idx = None
                entry_date = None
                entry_px = None

    return closed


def _compute_open_position_metrics(
    *,
    trading_dates: List[str],
    daily_results: List[Dict[str, Any]],
    close_prices: List[Optional[float]],
    aligned_equity: List[float],
) -> Dict[str, Any]:
    """Compute metrics for runs with no closed trades (long hold)."""
    shares_by_date: Dict[str, float] = {}
    for r in daily_results:
        d = str(r.get("trade_date") or "")
        if not d:
            continue
        try:
            sh = float(r.get("shares") or 0.0)
        except Exception:
            sh = 0.0
        shares_by_date[d] = sh

    weights: List[float] = []
    pos_values: List[float] = []
    held_days: List[str] = []
    for i, d in enumerate(trading_dates):
        sh = float(shares_by_date.get(d, 0.0) or 0.0)
        cp = close_prices[i] if i < len(close_prices) else None
        eq = float(aligned_equity[i]) if i < len(aligned_equity) else 0.0
        pv = float(sh) * float(cp) if (cp is not None and cp > 0 and sh > 1e-9) else 0.0
        if pv > 0 and eq > 0:
            weights.append(pv / eq)
            pos_values.append(pv)
            held_days.append(d)

    avg_weight = (sum(weights) / len(weights)) if weights else None
    max_weight = max(weights) if weights else None

    # Equity peak-to-trough drawdown while in position (calendar, based on aligned equity)
    dd_max = 0.0
    peak = None
    for i, d in enumerate(trading_dates):
        if d not in held_days:
            continue
        e = float(aligned_equity[i])
        if peak is None or e > peak:
            peak = e
        if peak and peak > 0:
            dd = (peak - e) / peak
            if dd > dd_max:
                dd_max = dd

    return {
        "avg_position_weight": avg_weight,
        "max_position_weight": max_weight,
        "held_days": len(held_days),
        "first_held_date": held_days[0] if held_days else None,
        "last_held_date": held_days[-1] if held_days else None,
        "max_drawdown_while_holding": float(dd_max) if dd_max is not None else None,
    }


def _sync_to_lean(
    signals_payload: Dict[str, Any],
    lean_workspace: Path,
    project_name: str,
) -> None:
    """Copy signals.json and main.py into the lean workspace."""
    project_dir = lean_workspace / project_name
    project_dir.mkdir(parents=True, exist_ok=True)

    signals_dir = project_dir / "signals"
    signals_dir.mkdir(parents=True, exist_ok=True)
    with open(signals_dir / "signals.json", "w", encoding="utf-8") as f:
        json.dump(signals_payload, f, ensure_ascii=False, indent=2, default=str)

    src_main = REPO_ROOT / "quantconnect" / "main.py"
    if src_main.exists():
        shutil.copy(src_main, project_dir / "main.py")


def _run_lean_backtest(lean_workspace: Path, project_name: str) -> bool:
    """Execute lean backtest and return success status."""
    ps_script = REPO_ROOT / "scripts" / "run_lean_no_proxy.ps1"
    if ps_script.exists():
        cmd = [
            "powershell", "-ExecutionPolicy", "Bypass", "-File",
            str(ps_script),
            "backtest", project_name, "--download-data",
        ]
    else:
        cmd = ["lean", "backtest", project_name, "--download-data"]

    print(f"  [LEAN] Running: {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=str(lean_workspace))
    return proc.returncode == 0


def _find_storage_dir(lean_workspace: Path, project_name: str) -> Path:
    """Locate the Object Store directory for the lean project."""
    return lean_workspace / "storage"


def _clear_storage_snapshots(storage_dir: Path) -> None:
    """Remove old snapshots before a fresh backtest run."""
    snapshots_dir = storage_dir / "snapshots"
    if snapshots_dir.exists():
        shutil.rmtree(snapshots_dir)


def _lean_custom_csv_path(lean_workspace: Path, symbol: str) -> Path:
    return lean_workspace / "data" / "custom" / f"{symbol.lower()}_daily.csv"


def _read_custom_trading_dates(csv_path: Path) -> List[str]:
    """Read trading dates from Lean custom CSV (column: date)."""
    if not csv_path.exists():
        return []
    dates: List[str] = []
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                d = (row.get("date") or "").strip()
                if d:
                    dates.append(d)
    except Exception as exc:
        print(f"[WARN] Failed reading custom CSV {csv_path}: {exc}")
        return []
    return sorted(set(dates))


def _check_custom_data_coverage(trading_dates: List[str], csv_path: Path) -> Dict[str, Any]:
    csv_dates = set(_read_custom_trading_dates(csv_path))
    missing_dates = [d for d in trading_dates if d not in csv_dates]
    total = len(trading_dates)
    covered = total - len(missing_dates)
    ratio = (covered / total) if total > 0 else 0.0
    return {
        "custom_csv_path": str(csv_path),
        "required_days": total,
        "covered_days": covered,
        "missing_days": len(missing_dates),
        "missing_dates": missing_dates,
        "coverage_ratio": ratio,
    }


def _auto_download_lean_custom_csv(
    symbol: str,
    start_date: str,
    end_date: str,
    output_csv: Path,
) -> bool:
    """Download missing Lean custom CSV data via bundled downloader."""
    downloader = REPO_ROOT / "scripts" / "runtime" / "download_yf_for_lean.py"
    cmd = [
        sys.executable,
        str(downloader),
        "--symbol",
        symbol,
        "--start",
        start_date,
        "--end",
        end_date,
        "--output",
        str(output_csv),
    ]
    print(f"[DATA] Running downloader: {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT))
    return proc.returncode == 0


def _write_performance_chart(
    symbol: str,
    trading_dates: List[str],
    aligned_equity: List[float],
    close_prices: List[Optional[float]],
    initial_cash: float,
    output_path: Path,
) -> Optional[Path]:
    """Write a chart comparing strategy return vs underlying price move."""
    try:
        import matplotlib.pyplot as plt  # Lazy import so runtime still works without plotting deps
    except Exception as exc:
        print(f"[WARN] Skip performance chart: matplotlib unavailable ({exc})")
        return None

    if not trading_dates:
        return None

    strategy_ret_pct = [((e / float(initial_cash)) - 1.0) * 100.0 for e in aligned_equity]

    # Underlying close-price move (%), aligned by trade_date with forward fill.
    aligned_close: List[float] = []
    last_close: Optional[float] = None
    for close in close_prices:
        if close is not None and close > 0:
            last_close = close
        aligned_close.append(last_close if last_close is not None else 0.0)

    first_close = next((c for c in aligned_close if c > 0), None)
    if first_close is None:
        price_ret_pct = [0.0 for _ in aligned_close]
    else:
        price_ret_pct = [((c / first_close) - 1.0) * 100.0 if c > 0 else 0.0 for c in aligned_close]

    x_dates = []
    for d in trading_dates:
        try:
            x_dates.append(datetime.strptime(d, "%Y-%m-%d").date())
        except Exception:
            x_dates.append(d)

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
    return output_path


def _write_equity_curve_chart(
    *,
    trading_dates: List[str],
    aligned_equity: List[float],
    initial_cash: float,
    output_path: Path,
    title: str,
) -> Optional[Path]:
    """仅画策略累计收益（%）。"""
    try:
        import matplotlib.pyplot as plt  # Lazy import
    except Exception as exc:
        print(f"[WARN] Skip equity curve chart: matplotlib unavailable ({exc})")
        return None
    if not trading_dates or not aligned_equity:
        return None
    x_dates = []
    for d in trading_dates:
        try:
            x_dates.append(datetime.strptime(d, "%Y-%m-%d").date())
        except Exception:
            x_dates.append(d)
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
    return output_path


def run_interleaved_backtest(
    symbol: str,
    start_date: str,
    end_date: str,
    db_path: str = "storage/db/memory.db",
    lean_workspace: Path = DEFAULT_LEAN_WORKSPACE,
    project_name: str = DEFAULT_LEAN_PROJECT,
    initial_cash: float = 100_000.0,
    enabled_analysts: Optional[List[str]] = None,
    experiment_id: Optional[str] = None,
    use_db_reports_only: bool = True,
    verbose: bool = False,
    graph_dump_dir: Optional[str] = None,
    report_output_root: Optional[str] = None,
    max_research_debate_rounds: Optional[int] = None,
    max_risk_debate_rounds: Optional[int] = None,
    llm_profile: Optional[str] = None,
    llm_model: Optional[str] = None,
    llm_temperature: Optional[float] = None,
    strategy_skills_mode: Optional[str] = None,
    strategy_skills_fallback_mode: Optional[str] = None,
    force_strategy_skill: Optional[str] = None,
    no_plot: bool = False,
    plot_subprocess: bool = True,
) -> Dict[str, Any]:
    """Run the full interleaved backtest loop."""

    print(f"\n{'='*80}")
    print("Agent-QC Interleaved Backtest")
    print(f"{'='*80}")
    print(f"Symbol: {symbol}  Range: {start_date} ~ {end_date}")
    print(f"Initial cash: ${initial_cash:,.0f}")
    _apply_strategy_skills_env(strategy_skills_mode, strategy_skills_fallback_mode, force_strategy_skill)

    enabled_analysts = _normalize_enabled_analysts(enabled_analysts)
    experiment_id = _derive_experiment_id(enabled_analysts, experiment_id)
    print(f"Enabled analysts: {enabled_analysts}")
    print(f"Experiment ID: {experiment_id}")

    runtime = _get_runtime_dependencies()
    DataAdapter = runtime["DataAdapter"]
    MemoryDBHelper = runtime["MemoryDBHelper"]
    create_trading_graph = runtime["create_trading_graph"]
    load_llm_from_config = runtime["load_llm_from_config"]

    cfg_path = str(REPO_ROOT / "config" / "config.yaml")
    llm = load_llm_from_config(
        cfg_path,
        llm_profile=llm_profile,
        llm_model=llm_model,
        llm_temperature=llm_temperature,
    )
    llm_meta = get_llm_metadata(
        config_path=cfg_path,
        profile=llm_profile,
        model_override=llm_model,
        temperature_override=llm_temperature,
    )
    strategy_skills_meta = get_strategy_skills_config(
        config_path=cfg_path,
        mode_override=strategy_skills_mode,
        fallback_mode_override=strategy_skills_fallback_mode,
        force_skill_override=force_strategy_skill,
    )
    print(
        "Strategy skills: "
        f"mode={strategy_skills_meta['mode']} fallback={strategy_skills_meta['fallback_mode']} "
        f"force={strategy_skills_meta.get('force_skill') or '-'}"
    )
    data_adapter = DataAdapter(use_cache=True)
    trading_dates_resolver = lambda end, n: data_adapter.get_last_n_trading_days(end, n)
    db_helper = MemoryDBHelper(db_path, trading_dates_resolver=trading_dates_resolver)
    memory = create_hybrid_trading_memory(
        db_path,
        symbol,
        config_path=REPO_ROOT / "config" / "config.yaml",
    )

    trading_dates = get_trading_dates(start_date, end_date, data_adapter)
    if not trading_dates:
        print("[ERROR] No trading dates found")
        memory.close()
        db_helper.close()
        return {}

    print(f"Trading dates: {len(trading_dates)} ({trading_dates[0]} ~ {trading_dates[-1]})")

    custom_csv = _lean_custom_csv_path(lean_workspace, symbol)
    data_coverage = _check_custom_data_coverage(trading_dates, custom_csv)
    auto_download_performed = False
    if data_coverage["missing_days"] > 0:
        print(
            "[DATA] Lean custom CSV coverage incomplete: "
            f"{data_coverage['covered_days']}/{data_coverage['required_days']} "
            f"({data_coverage['coverage_ratio']:.1%})"
        )
        print(f"[DATA] Missing dates (first 10): {data_coverage['missing_dates'][:10]}")
        auto_download_performed = True
        ok = _auto_download_lean_custom_csv(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            output_csv=custom_csv,
        )
        if not ok:
            print("[ERROR] Auto-download failed; aborting interleaved backtest")
            memory.close()
            db_helper.close()
            return {}
        data_coverage = _check_custom_data_coverage(trading_dates, custom_csv)
        if data_coverage["missing_days"] > 0:
            print(
                "[ERROR] Lean custom CSV still incomplete after auto-download: "
                f"{data_coverage['covered_days']}/{data_coverage['required_days']} "
                f"({data_coverage['coverage_ratio']:.1%})"
            )
            print(f"[ERROR] Missing dates: {data_coverage['missing_dates']}")
            memory.close()
            db_helper.close()
            return {}
        print("[DATA] Lean custom CSV coverage verified after auto-download")
    else:
        print("[DATA] Lean custom CSV coverage verified")

    storage_dir = _find_storage_dir(lean_workspace, project_name)
    _clear_storage_snapshots(storage_dir)

    # Preload close prices from Lean custom CSV for benchmark/alpha context
    close_prices_pre = _read_close_prices_from_lean_custom_csv(
        trading_dates=trading_dates,
        lean_workspace=lean_workspace,
        symbol=symbol,
    )
    close_by_date: Dict[str, Optional[float]] = {
        d: (close_prices_pre[idx] if idx < len(close_prices_pre) else None)
        for idx, d in enumerate(trading_dates)
    }
    first_close_for_bh = next((c for c in close_prices_pre if c is not None and c > 0), None)

    all_signals: Dict[str, Dict[str, Any]] = {}
    current_position: Optional[Dict[str, Any]] = None
    portfolio_state: Optional[Dict[str, Any]] = {
        "total_value": initial_cash,
        "cash": initial_cash,
        "positions_value": 0.0,
        "total_return": 0.0,
    }

    results: List[Dict[str, Any]] = []
    missing_snapshot_days: List[str] = []
    last_fill_trade_date: Optional[str] = None

    for i, trade_date in enumerate(trading_dates, 1):
        print(f"\n{'─'*60}")
        print(f"[Day {i}/{len(trading_dates)}] {trade_date}")
        print(f"{'─'*60}")

        # Inject rolling benchmark/alpha context into portfolio_state so Trader/Risk can see it.
        if portfolio_state and isinstance(portfolio_state, dict):
            last_close = close_by_date.get(trade_date)
            bh_cum: Optional[float] = None
            alpha_vs_bh: Optional[float] = None
            try:
                tv = float(portfolio_state.get("total_value") or 0.0)
                strat_cum = (tv / float(initial_cash)) - 1.0 if initial_cash and initial_cash > 0 else 0.0
                if first_close_for_bh and last_close and first_close_for_bh > 0 and last_close > 0:
                    bh_cum = (float(last_close) / float(first_close_for_bh)) - 1.0
                    alpha_vs_bh = strat_cum - bh_cum
            except Exception:
                bh_cum = None
                alpha_vs_bh = None
            portfolio_state["benchmark_buy_hold_cum_return"] = bh_cum
            portfolio_state["alpha_vs_buy_hold"] = alpha_vs_bh
            portfolio_state["benchmark_first_close"] = first_close_for_bh
            portfolio_state["benchmark_last_close"] = last_close

        # 1) Create the graph for this day
        graph = create_trading_graph(
            llm,
            memory,
            db_helper,
            max_research_debate_rounds=max_research_debate_rounds,
            max_risk_debate_rounds=max_risk_debate_rounds,
        )

        # 2) Run single-day agent
        signal = run_single_day(
            trade_date=trade_date,
            symbol=symbol,
            current_position=current_position,
            portfolio_state=portfolio_state,
            graph=graph,
            data_adapter=data_adapter,
            db_helper=db_helper,
            enabled_analysts=enabled_analysts,
            experiment_id=experiment_id,
            use_db_reports_only=use_db_reports_only,
            verbose=verbose,
            graph_dump_dir=graph_dump_dir,
            report_output_root=report_output_root,
            llm=llm,
        )

        # 3) Accumulate signals
        execution_date = signal.get("execution_date")
        if execution_date:
            all_signals[str(execution_date)] = signal

        signals_payload = {
            "symbol": symbol,
            "export_mode": "backtest",
            "start_date": start_date,
            "end_date": end_date,
            "experiment_id": experiment_id,
            "enabled_analysts": enabled_analysts,
            "strategy_skills": strategy_skills_meta,
            "by_execution_date": all_signals,
        }

        # 4) Sync to lean workspace and run backtest
        _sync_to_lean(signals_payload, lean_workspace, project_name)
        print(f"  [SYNC] Signals synced ({len(all_signals)} total)")

        lean_success = _run_lean_backtest(lean_workspace, project_name)
        if not lean_success:
            print(f"  [WARN] Lean backtest failed for day {trade_date}, continuing with last known state")

        # 5) Parse QC snapshot
        snapshot = parse_daily_snapshot(storage_dir, trade_date, symbol)
        if snapshot is None:
            exec_date_str = str(execution_date) if execution_date else ""
            if exec_date_str:
                snapshot = parse_daily_snapshot(storage_dir, exec_date_str, symbol)

        if snapshot is not None:
            current_position, portfolio_state = snapshot_to_agent_fields(snapshot, initial_cash)
            print(f"  [QC] Equity: ${snapshot.equity:,.2f}  Cash: ${snapshot.cash:,.2f}  "
                  f"Shares: {snapshot.shares:.0f}  PnL: ${snapshot.unrealized_pnl:,.2f}")

            if snapshot.filled_today:
                last_fill_trade_date = trade_date

            # 6) Persist to DB
            fill_price = None
            fill_qty = None
            if snapshot.filled_today:
                fill_price = snapshot.filled_today[0].get("fill_price")
                fill_qty = snapshot.filled_today[0].get("quantity")

            db_helper.upsert_portfolio_snapshot(
                symbol=symbol,
                trade_date=trade_date,
                experiment_id=experiment_id,
                source="qc_real",
                equity=snapshot.equity,
                cash=snapshot.cash,
                shares=snapshot.shares,
                avg_price=snapshot.avg_price,
                market_price=snapshot.market_price,
                unrealized_pnl=snapshot.unrealized_pnl,
                unrealized_pnl_pct=snapshot.unrealized_pnl_pct,
                signal_action=signal.get("action"),
                fill_price=fill_price,
                fill_qty=fill_qty,
                snapshot_json=json.dumps({
                    "signal": signal,
                    "pending_orders": snapshot.pending_orders,
                    "filled_today": snapshot.filled_today,
                }, default=str),
            )
        else:
            print(f"  [WARN] No QC snapshot found for {trade_date}, keeping previous state")
            missing_snapshot_days.append(trade_date)

        # Daily observability fields (so we don't need Lean logs for post-mortem)
        entry_type = (signal.get("entry_type") or "MKT_OPEN")
        target_pct = signal.get("target_pct")
        entry_price = signal.get("entry_price")
        pending_orders = snapshot.pending_orders if snapshot else []
        pending_prices: List[float] = []
        if isinstance(pending_orders, list):
            for o in pending_orders:
                if not isinstance(o, dict):
                    continue
                lp = o.get("limit_price")
                try:
                    v = float(lp) if lp is not None else None
                except Exception:
                    v = None
                if v is not None and v > 0:
                    pending_prices.append(v)

        last_fill_offset_days: Optional[int] = None
        if last_fill_trade_date:
            try:
                last_fill_offset_days = (datetime.strptime(trade_date, "%Y-%m-%d") - datetime.strptime(last_fill_trade_date, "%Y-%m-%d")).days
            except Exception:
                last_fill_offset_days = None

        results.append({
            "trade_date": trade_date,
            "signal_action": signal.get("action", "HOLD"),
            "execution_date": str(execution_date) if execution_date else None,
            "equity": snapshot.equity if snapshot else None,
            "shares": snapshot.shares if snapshot else None,
            "target_pct": float(target_pct) if target_pct is not None else None,
            "entry_type": str(entry_type),
            "market_regime": signal.get("market_regime"),
            "selected_skill": signal.get("selected_skill"),
            "regime_confidence": (
                float(signal.get("regime_confidence"))
                if signal.get("regime_confidence") is not None
                else None
            ),
            "regime_evidence": signal.get("regime_evidence") or [],
            "skill_router_mode": signal.get("skill_router_mode"),
            "forced_selected_skill": signal.get("forced_selected_skill"),
            "reflection_market_regime": signal.get("reflection_market_regime"),
            "reflection_selected_skill": signal.get("reflection_selected_skill"),
            "reflection_confidence": (
                float(signal.get("reflection_confidence"))
                if signal.get("reflection_confidence") is not None
                else None
            ),
            "reflection_evidence": signal.get("reflection_evidence") or [],
            "limit_price": float(entry_price) if entry_type == "LIMIT" and entry_price is not None else None,
            "cancel_pending_orders": bool(signal.get("cancel_pending_orders")) if "cancel_pending_orders" in signal else None,
            "reason": signal.get("reason"),
            "pending_orders_count": len(pending_orders) if isinstance(pending_orders, list) else None,
            "pending_order_limits": pending_prices[:10],
            "filled_today_count": len(snapshot.filled_today) if (snapshot and snapshot.filled_today) else 0,
            "last_fill_offset_days": last_fill_offset_days,
        })

    # Final summary
    print(f"\n{'='*80}")
    print("Interleaved Backtest Complete")
    print(f"{'='*80}")

    if portfolio_state:
        print(f"Final equity: ${portfolio_state.get('total_value', 0):,.2f}")
        print(f"Total return: {portfolio_state.get('total_return', 0):.2f}%")

    summary = {
        "symbol": symbol,
        "start_date": start_date,
        "end_date": end_date,
        "experiment_id": experiment_id,
        "initial_cash": initial_cash,
        "llm": llm_meta,
        "strategy_skills": strategy_skills_meta,
        "final_portfolio_state": portfolio_state,
        "final_position": current_position,
        "trading_days": len(trading_dates),
        "signals_count": len(all_signals),
        "daily_results": results,
        "data_coverage": {
            **data_coverage,
            "auto_download_performed": auto_download_performed,
        },
        "snapshot_coverage": {
            "missing_snapshot_days": missing_snapshot_days,
            "missing_snapshot_count": len(missing_snapshot_days),
            "snapshot_coverage_ratio": (
                (len(trading_dates) - len(missing_snapshot_days)) / len(trading_dates)
                if trading_dates
                else 0.0
            ),
        },
    }

    output_dir = REPO_ROOT / "storage" / "interleaved_backtests"
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_path = output_dir / f"interleaved_{symbol}_{ts}.json"

    # --- Metrics + CSV export (aligned daily series) ---
    aligned_equity = _align_equity_series(
        trading_dates=trading_dates,
        daily_results=results,
        initial_cash=float(initial_cash),
    )
    close_prices = close_prices_pre
    closed_trades = _infer_closed_trades_from_shares(
        daily_results=results,
        close_prices=close_prices,
    )
    metrics = compute_metrics(
        daily_equity=aligned_equity,
        daily_dates=trading_dates,
        initial_cash=float(initial_cash),
        closed_trades=closed_trades,
        first_date=trading_dates[0],
        last_date=trading_dates[-1],
    )
    summary["metrics"] = metrics
    summary["daily_dates"] = list(trading_dates)
    summary["daily_equity"] = list(aligned_equity)
    summary["daily_returns"] = list(metrics.get("daily_returns") or [])
    summary["cumulative_returns"] = list(metrics.get("cumulative_returns") or [])

    # Open-position metrics (useful when trade_count==0)
    try:
        summary["open_position_metrics"] = _compute_open_position_metrics(
            trading_dates=trading_dates,
            daily_results=results,
            close_prices=close_prices,
            aligned_equity=aligned_equity,
        )
    except Exception:
        summary["open_position_metrics"] = {}

    # --- Benchmark & behavior metrics ---
    bh_total_return: Optional[float] = None
    alpha_vs_bh: Optional[float] = None
    try:
        first_close = next((c for c in close_prices if c is not None and c > 0), None)
        last_close = next((c for c in reversed(close_prices) if c is not None and c > 0), None)
        if first_close and last_close and first_close > 0:
            bh_total_return = (float(last_close) / float(first_close)) - 1.0
            alpha_vs_bh = float(metrics.get("total_return") or 0.0) - float(bh_total_return)
    except Exception:
        bh_total_return = None
        alpha_vs_bh = None

    # Unfilled ratio (approx): pending limit orders remaining / total LIMIT signals
    limit_signal_count = 0
    for r in results:
        et = str(r.get("entry_type") or "")
        if et.upper() == "LIMIT" and str(r.get("signal_action") or "").upper() in {"BUY", "SELL"}:
            limit_signal_count += 1
    final_pending = 0
    try:
        final_pending = len((summary.get("final_position") or {}).get("pending_orders") or [])
    except Exception:
        final_pending = 0
    unfilled_ratio = (final_pending / limit_signal_count) if limit_signal_count > 0 else None

    # Average limit offset vs close (only for LIMIT signals with price)
    offsets: List[float] = []
    close_by_date = {d: close_prices[i] for i, d in enumerate(trading_dates) if i < len(close_prices)}
    for r in results:
        if str(r.get("entry_type") or "").upper() != "LIMIT":
            continue
        lp = r.get("limit_price")
        d = str(r.get("trade_date") or "")
        cp = close_by_date.get(d)
        try:
            lp_f = float(lp) if lp is not None else None
        except Exception:
            lp_f = None
        if cp is not None and cp > 0 and lp_f is not None and lp_f > 0:
            offsets.append(abs(cp - lp_f) / cp)
    avg_limit_offset_pct = (sum(offsets) / len(offsets)) if offsets else None

    # In-market days ratio: shares > 0 days / total trading days
    in_market_days = sum(1 for r in results if (r.get("shares") is not None and float(r.get("shares") or 0) > 1e-9))
    in_market_days_ratio = (in_market_days / len(trading_dates)) if trading_dates else None

    summary["benchmark"] = {
        "buy_hold_total_return": bh_total_return,
        "alpha_vs_buy_hold": alpha_vs_bh,
        "first_close": first_close,
        "last_close": last_close,
    }
    summary["behavior_metrics"] = {
        "limit_signal_count": limit_signal_count,
        "final_pending_orders": final_pending,
        "unfilled_ratio_approx": unfilled_ratio,
        "avg_limit_offset_pct": avg_limit_offset_pct,
        "in_market_days": in_market_days,
        "in_market_days_ratio": in_market_days_ratio,
    }

    try:
        total_pct = float(metrics.get("total_return") or 0.0) * 100.0
        cagr_val = metrics.get("cagr")
        sharpe_val = metrics.get("sharpe")
        max_dd = float(metrics.get("max_drawdown") or 0.0) * 100.0
        print(
            f"[OK] Metrics -> total={total_pct:.2f}% "
            f"CAGR={cagr_val if cagr_val is not None else 'NA'} "
            f"Sharpe={sharpe_val if sharpe_val is not None else 'NA'} "
            f"MaxDD={max_dd:.2f}%"
        )
    except Exception:
        pass

    # Write JSON before optional CSV/plots so visualization issues never discard core results.
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n[OK] Results saved to {out_path}")

    csv_path = out_path.with_suffix(".csv")
    try:
        _write_interleaved_observability_csv(
            path=csv_path,
            results=results,
            trading_dates=trading_dates,
            aligned_equity=aligned_equity,
            initial_cash=float(initial_cash),
            close_prices=close_prices,
            daily_returns=list(summary["daily_returns"]),
            cumulative_returns=list(summary["cumulative_returns"]),
        )
        print(f"[OK] Equity CSV saved to {csv_path}")
    except Exception as exc:
        print(f"[WARN] Equity CSV export failed: {exc}")

    if not no_plot:
        if plot_subprocess:
            # Plot in a child process to avoid OpenMP/matplotlib crashes impacting the main run.
            plotter = REPO_ROOT / "scripts" / "runtime" / "plot_interleaved_charts.py"
            try:
                payload_for_plot = dict(summary)
                payload_for_plot["close_prices"] = close_prices
                tmp_json = out_path.with_name(out_path.stem + "_plot.json")
                with open(tmp_json, "w", encoding="utf-8") as f:
                    json.dump(payload_for_plot, f, ensure_ascii=False, indent=2, default=str)
                proc = subprocess.run(
                    [sys.executable, str(plotter), "--input-json", str(tmp_json), "--out-dir", str(output_dir)],
                    cwd=str(REPO_ROOT),
                )
                if proc.returncode == 0:
                    print("[OK] Charts generated (subprocess)")
                else:
                    print(f"[WARN] Chart subprocess failed (exit={proc.returncode})")
            except Exception as exc:
                print(f"[WARN] Chart subprocess failed: {exc}")
        else:
            chart_path = output_dir / f"interleaved_{symbol}_{ts}_return_vs_price.png"
            chart_written = _write_performance_chart(
                symbol=symbol,
                trading_dates=trading_dates,
                aligned_equity=aligned_equity,
                close_prices=close_prices,
                initial_cash=float(initial_cash),
                output_path=chart_path,
            )
            if chart_written:
                print(f"[OK] Performance chart saved to {chart_written}")

            equity_png = output_dir / f"interleaved_{symbol}_{ts}_equity_curve.png"
            eq_chart = _write_equity_curve_chart(
                trading_dates=trading_dates,
                aligned_equity=aligned_equity,
                initial_cash=float(initial_cash),
                output_path=equity_png,
                title=f"Interleaved Backtest: {symbol} Cumulative Return",
            )
            if eq_chart:
                print(f"[OK] Equity curve chart saved to {eq_chart}")

    if missing_snapshot_days:
        ratio = summary["snapshot_coverage"]["snapshot_coverage_ratio"]
        print(
            "[WARN] Snapshot coverage is incomplete: "
            f"{ratio:.1%} ({len(trading_dates) - len(missing_snapshot_days)}/{len(trading_dates)})"
        )

    memory.close()
    db_helper.close()

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Agent-QC interleaved backtest: agent decides daily, QC executes, real results feed back.",
    )
    parser.add_argument("--symbol", type=str, default="NVDA")
    parser.add_argument("--start", type=str, default="2025-01-02")
    parser.add_argument("--end", type=str, default="2025-01-10")
    parser.add_argument("--db", type=str, default="storage/db/memory.db")
    parser.add_argument("--lean-workspace", type=str, default=str(DEFAULT_LEAN_WORKSPACE))
    parser.add_argument("--project-name", type=str, default=DEFAULT_LEAN_PROJECT)
    parser.add_argument("--initial-cash", type=float, default=100_000.0)
    parser.add_argument(
        "--enabled-analysts",
        type=str,
        default="market,news,sentiment,fundamentals",
    )
    parser.add_argument("--experiment-id", type=str, default=None)
    parser.add_argument(
        "--use-db-reports-only",
        action="store_true",
        default=True,
    )
    parser.add_argument(
        "--no-db-reports-only",
        action="store_false",
        dest="use_db_reports_only",
    )
    parser.add_argument("--report-output-root", type=str, default=None)
    parser.add_argument("--graph-dump", type=str, default=None)
    parser.add_argument("--max-research-debate-rounds", type=int, default=None)
    parser.add_argument("--max-risk-debate-rounds", type=int, default=None)
    parser.add_argument("--llm-profile", type=str, default=None, help="Select llm.silicon profile from config.yaml")
    parser.add_argument("--llm-model", type=str, default=None, help="Override model_name (e.g. THUDM/glm-4-9b-chat)")
    parser.add_argument("--llm-temperature", type=float, default=None, help="Override temperature (float)")
    parser.add_argument("--strategy-skills-mode", choices=("reflect", "all", "off"), default=None)
    parser.add_argument("--strategy-skills-fallback-mode", choices=("all", "off"), default=None)
    parser.add_argument(
        "--force-strategy-skill",
        choices=(
            "strong_uptrend_skill",
            "range_bound_skill",
            "downtrend_skill",
            "high_vol_uncertain_skill",
        ),
        default=None,
    )
    parser.add_argument("--no-plot", action="store_true", help="Skip chart generation (avoid matplotlib/OpenMP issues)")
    parser.add_argument(
        "--plot-subprocess",
        action="store_true",
        default=True,
        help="Generate charts in a subprocess (default True)",
    )
    parser.add_argument(
        "--no-plot-subprocess",
        action="store_false",
        dest="plot_subprocess",
        help="Generate charts in-process (may hit OpenMP issues)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    enabled_analysts = [a.strip() for a in args.enabled_analysts.split(",") if a.strip()]

    run_interleaved_backtest(
        symbol=args.symbol,
        start_date=args.start,
        end_date=args.end,
        db_path=args.db,
        lean_workspace=Path(args.lean_workspace),
        project_name=args.project_name,
        initial_cash=args.initial_cash,
        enabled_analysts=enabled_analysts,
        experiment_id=args.experiment_id,
        use_db_reports_only=args.use_db_reports_only,
        verbose=args.verbose,
        graph_dump_dir=args.graph_dump,
        report_output_root=args.report_output_root,
        max_research_debate_rounds=args.max_research_debate_rounds,
        max_risk_debate_rounds=args.max_risk_debate_rounds,
        llm_profile=args.llm_profile,
        llm_model=args.llm_model,
        llm_temperature=args.llm_temperature,
        strategy_skills_mode=args.strategy_skills_mode,
        strategy_skills_fallback_mode=args.strategy_skills_fallback_mode,
        force_strategy_skill=args.force_strategy_skill,
        no_plot=args.no_plot,
        plot_subprocess=args.plot_subprocess,
    )


if __name__ == "__main__":
    main()
