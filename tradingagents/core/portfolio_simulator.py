#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
单标的、简化的组合模拟（与 QC set_holdings 的「目标仓位比例」语义对齐）。

用于 run_signal_export 在多日循环中注入 current_position / portfolio_state，
使 Trader、risk_manager 的 prompt 与 resolve_signal 的 is_holding 一致。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple


@dataclass
class PortfolioSimulator:
    symbol: str
    initial_cash: float = 100_000.0
    cash: float = field(init=False)
    shares: float = 0.0
    avg_entry_price: float = 0.0
    entry_date: str = ""

    def __post_init__(self) -> None:
        self.cash = float(self.initial_cash)

    def equity_at_price(self, price: float) -> float:
        if price is None or price <= 0:
            return max(self.cash, 0.0)
        return float(self.cash) + float(self.shares) * float(price)

    def is_holding(self, price: Optional[float] = None) -> bool:
        if self.shares > 1e-9:
            return True
        return False

    def apply_fill(
        self,
        action: str,
        target_pct: float,
        execution_price: Optional[float],
    ) -> None:
        """
        在 execution_price 处按信号更新仓位。BUY 时按组合权益 * target_pct 配置标的市值；SELL 清仓。
        """
        act = (action or "HOLD").upper()
        if execution_price is None or execution_price <= 0:
            return
        p = float(execution_price)
        tgt = max(0.0, min(1.0, float(target_pct)))

        equity = self.equity_at_price(p)
        if act == "SELL":
            proceeds = self.shares * p
            self.cash = float(self.cash) + proceeds
            self.shares = 0.0
            self.avg_entry_price = 0.0
            self.entry_date = ""
            return

        if act != "BUY":
            return

        target_shares = (equity * tgt) / p if p > 0 else 0.0
        delta = target_shares - self.shares
        if delta > 1e-12:
            cost = delta * p
            if cost <= self.cash + 1e-6:
                old_notional = self.shares * self.avg_entry_price if self.shares > 0 and self.avg_entry_price > 0 else 0.0
                new_notional = old_notional + delta * p
                self.shares = target_shares
                self.cash = float(self.cash) - cost
                self.avg_entry_price = new_notional / self.shares if self.shares > 1e-12 else 0.0
        elif delta < -1e-12:
            sell_qty = min(self.shares, -delta)
            self.cash += sell_qty * p
            self.shares -= sell_qty
            if self.shares <= 1e-9:
                self.shares = 0.0
                self.avg_entry_price = 0.0
                self.entry_date = ""

    def to_agent_fields(
        self,
        trade_date: str,
        mark_price: Optional[float],
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        生成 AgentState 的 current_position、portfolio_state；无仓且无现金异常时仍可返回组合壳。
        """
        mp = float(mark_price) if mark_price is not None and mark_price > 0 else None
        positions_value = (self.shares * mp) if mp is not None else 0.0
        total_value = float(self.cash) + positions_value
        total_return = (
            ((total_value - self.initial_cash) / self.initial_cash * 100.0)
            if self.initial_cash > 0
            else 0.0
        )

        portfolio_state: Dict[str, Any] = {
            "total_value": total_value,
            "cash": float(self.cash),
            "positions_value": positions_value,
            "total_return": total_return,
        }

        if self.shares <= 1e-9 or mp is None:
            return None, portfolio_state

        entry = self.avg_entry_price if self.avg_entry_price > 0 else mp
        pnl = self.shares * (mp - entry)
        pnl_pct = ((mp - entry) / entry * 100.0) if entry > 0 else 0.0

        current_position: Dict[str, Any] = {
            "shares": self.shares,
            "entry_price": entry,
            "entry_date": self.entry_date or trade_date,
            "current_price": mp,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "stop_loss_price": None,
            "take_profit_price": None,
        }
        return current_position, portfolio_state

    def set_entry_date_after_buy(self, execution_date: str) -> None:
        if self.shares > 1e-9:
            self.entry_date = execution_date
