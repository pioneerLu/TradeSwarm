"""
Parse Lean/QuantConnect backtest outputs to extract real portfolio state.

Primary source: Object Store snapshots written by the enhanced QC algorithm.
Fallback: order-events.json + equity curve from summary.json.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class PortfolioSnapshot:
    date: str
    symbol: str
    equity: float
    cash: float
    shares: float = 0.0
    avg_price: float = 0.0
    market_price: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    pending_orders: List[Dict[str, Any]] = field(default_factory=list)
    filled_today: List[Dict[str, Any]] = field(default_factory=list)


def parse_daily_snapshot(
    storage_dir: Path,
    date: str,
    symbol: str,
) -> Optional[PortfolioSnapshot]:
    """Read a daily snapshot from Object Store (lean_workspace/storage/)."""
    snapshot_path = storage_dir / "snapshots" / f"{date}.json"
    if not snapshot_path.exists():
        return None

    with open(snapshot_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    sym = symbol.upper()
    holdings = data.get("holdings", {})
    h = holdings.get(sym, {})

    return PortfolioSnapshot(
        date=data.get("date", date),
        symbol=sym,
        equity=float(data.get("equity", 0)),
        cash=float(data.get("cash", 0)),
        shares=float(h.get("shares", 0)),
        avg_price=float(h.get("avg_price", 0)),
        market_price=float(h.get("market_price", 0)),
        market_value=float(h.get("market_value", 0)),
        unrealized_pnl=float(h.get("unrealized_pnl", 0)),
        unrealized_pnl_pct=float(h.get("unrealized_pnl_pct", 0)),
        pending_orders=data.get("pending_orders", []),
        filled_today=data.get("filled_today", []),
    )


def parse_latest_snapshot(
    storage_dir: Path,
    symbol: str,
) -> Optional[PortfolioSnapshot]:
    """Find the most recent snapshot in Object Store."""
    snapshots_dir = storage_dir / "snapshots"
    if not snapshots_dir.exists():
        return None

    files = sorted(snapshots_dir.glob("*.json"), reverse=True)
    for f in files:
        date = f.stem
        snap = parse_daily_snapshot(storage_dir, date, symbol)
        if snap is not None:
            return snap
    return None


def snapshot_to_agent_fields(
    snapshot: Optional[PortfolioSnapshot],
    initial_cash: float = 100_000.0,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Convert a PortfolioSnapshot to AgentState current_position / portfolio_state."""
    if snapshot is None:
        ps = {
            "total_value": initial_cash,
            "cash": initial_cash,
            "positions_value": 0.0,
            "total_return": 0.0,
        }
        return None, ps

    total_return = (
        ((snapshot.equity - initial_cash) / initial_cash * 100.0)
        if initial_cash > 0
        else 0.0
    )

    portfolio_state: Dict[str, Any] = {
        "total_value": snapshot.equity,
        "cash": snapshot.cash,
        "positions_value": snapshot.market_value,
        "total_return": total_return,
    }

    if snapshot.shares <= 1e-9:
        return None, portfolio_state

    current_position: Dict[str, Any] = {
        "shares": snapshot.shares,
        "entry_price": snapshot.avg_price,
        "entry_date": "",
        "current_price": snapshot.market_price,
        "pnl": snapshot.unrealized_pnl,
        "pnl_pct": snapshot.unrealized_pnl_pct,
        "stop_loss_price": None,
        "take_profit_price": None,
        "pending_orders": snapshot.pending_orders,
        "filled_today": snapshot.filled_today,
    }
    return current_position, portfolio_state


def parse_order_events_fallback(
    backtest_dir: Path,
    symbol: str,
    target_date: str,
    initial_cash: float = 100_000.0,
) -> Optional[PortfolioSnapshot]:
    """Fallback: reconstruct portfolio from order-events.json + equity curve."""
    events_files = list(backtest_dir.glob("*-order-events.json"))
    summary_files = list(backtest_dir.glob("*-summary.json"))
    if not events_files or not summary_files:
        return None

    with open(events_files[0], "r", encoding="utf-8") as f:
        events = json.load(f)

    cash = initial_cash
    shares = 0.0
    avg_price = 0.0

    from datetime import datetime
    target_ts = datetime.strptime(target_date, "%Y-%m-%d").timestamp()

    for evt in events:
        if evt.get("status") != "filled":
            continue
        evt_ts = evt.get("time", 0)
        if evt_ts > target_ts + 86400:
            break

        fill_qty = float(evt.get("fillQuantity", 0))
        fill_price = float(evt.get("fillPrice", 0))
        if fill_qty > 0:
            cost = fill_qty * fill_price
            old_notional = shares * avg_price
            shares += fill_qty
            avg_price = (old_notional + cost) / shares if shares > 0 else 0
            cash -= cost
        elif fill_qty < 0:
            proceeds = abs(fill_qty) * fill_price
            shares += fill_qty
            cash += proceeds
            if shares <= 1e-9:
                shares = 0.0
                avg_price = 0.0

    with open(summary_files[0], "r", encoding="utf-8") as f:
        summary = json.load(f)

    equity_data = (
        summary.get("charts", {})
        .get("Strategy Equity", {})
        .get("series", {})
        .get("Equity", {})
        .get("values", [])
    )
    equity = initial_cash
    market_price = avg_price
    for pt in equity_data:
        ts = pt[0]
        if ts <= target_ts + 86400:
            equity = pt[4]

    market_value = shares * market_price if shares > 0 else 0.0

    return PortfolioSnapshot(
        date=target_date,
        symbol=symbol.upper(),
        equity=equity,
        cash=cash,
        shares=shares,
        avg_price=avg_price,
        market_price=market_price,
        market_value=market_value,
        unrealized_pnl=(market_price - avg_price) * shares if shares > 0 else 0.0,
        unrealized_pnl_pct=((market_price - avg_price) / avg_price * 100) if avg_price > 0 and shares > 0 else 0.0,
    )
