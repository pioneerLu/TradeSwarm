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
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.runtime.run_signal_export import (  # noqa: E402
    DatabaseMemory,
    _get_runtime_dependencies,
    _normalize_enabled_analysts,
    _derive_experiment_id,
    _validate_signal,
    get_trading_dates,
    run_single_day,
)
from tradingagents.core.lean_result_parser import (  # noqa: E402
    parse_daily_snapshot,
    parse_latest_snapshot,
    snapshot_to_agent_fields,
)


DEFAULT_LEAN_WORKSPACE = REPO_ROOT / "lean_workspace"
DEFAULT_LEAN_PROJECT = "TradeSwarm"


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
) -> Dict[str, Any]:
    """Run the full interleaved backtest loop."""

    print(f"\n{'='*80}")
    print("Agent-QC Interleaved Backtest")
    print(f"{'='*80}")
    print(f"Symbol: {symbol}  Range: {start_date} ~ {end_date}")
    print(f"Initial cash: ${initial_cash:,.0f}")

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
    llm = load_llm_from_config(cfg_path)
    data_adapter = DataAdapter(use_cache=True)
    trading_dates_resolver = lambda end, n: data_adapter.get_last_n_trading_days(end, n)
    db_helper = MemoryDBHelper(db_path, trading_dates_resolver=trading_dates_resolver)
    memory = DatabaseMemory(db_path=db_path, symbol=symbol)

    trading_dates = get_trading_dates(start_date, end_date, data_adapter)
    if not trading_dates:
        print("[ERROR] No trading dates found")
        return {}

    print(f"Trading dates: {len(trading_dates)} ({trading_dates[0]} ~ {trading_dates[-1]})")

    storage_dir = _find_storage_dir(lean_workspace, project_name)
    _clear_storage_snapshots(storage_dir)

    all_signals: Dict[str, Dict[str, Any]] = {}
    current_position: Optional[Dict[str, Any]] = None
    portfolio_state: Optional[Dict[str, Any]] = {
        "total_value": initial_cash,
        "cash": initial_cash,
        "positions_value": 0.0,
        "total_return": 0.0,
    }

    results: List[Dict[str, Any]] = []

    for i, trade_date in enumerate(trading_dates, 1):
        print(f"\n{'─'*60}")
        print(f"[Day {i}/{len(trading_dates)}] {trade_date}")
        print(f"{'─'*60}")

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

        results.append({
            "trade_date": trade_date,
            "signal_action": signal.get("action", "HOLD"),
            "execution_date": str(execution_date) if execution_date else None,
            "equity": snapshot.equity if snapshot else None,
            "shares": snapshot.shares if snapshot else None,
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
        "final_portfolio_state": portfolio_state,
        "final_position": current_position,
        "trading_days": len(trading_dates),
        "signals_count": len(all_signals),
        "daily_results": results,
    }

    output_dir = REPO_ROOT / "storage" / "interleaved_backtests"
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_path = output_dir / f"interleaved_{symbol}_{ts}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n[OK] Results saved to {out_path}")

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
    )


if __name__ == "__main__":
    main()
