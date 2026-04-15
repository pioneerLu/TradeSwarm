#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Daily trading summary builder.

目的：
- 把“每日一次”的 agent 决策链（research/risk/trader/signal）与组合状态快照
  归一化成一行可写入 memory.db 的 daily_trading_summaries。
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from tradingagents.agents.utils.agentstate.agent_states import AgentState
from tradingagents.agents.utils.json_parser import extract_json_from_text


def _safe_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _clip_pct(value: Optional[float], default: float = 0.0) -> float:
    if value is None:
        return float(default)
    return max(0.0, min(1.0, float(value)))


def _to_pct_return(prev_equity: Optional[float], equity: Optional[float]) -> Optional[float]:
    if prev_equity is None or equity is None:
        return None
    try:
        pe = float(prev_equity)
        e = float(equity)
        if pe <= 0:
            return None
        return (e - pe) / pe * 100.0
    except Exception:
        return None


def _summarize_positioning(signal_action: str, portfolio_state: Optional[Dict[str, Any]]) -> str:
    act = (signal_action or "HOLD").upper()
    shares = None
    if portfolio_state and isinstance(portfolio_state, dict):
        # interleaved: portfolio_state from snapshot_to_agent_fields uses {"shares": ...} in current_position,
        # but we only get portfolio_state here; keep it robust.
        shares = portfolio_state.get("shares")
    sh = _safe_float(shares)
    has_pos = (sh is not None and sh > 1e-9)

    if act == "SELL":
        return "sold" if has_pos else "empty"
    if act == "BUY":
        return "partial" if has_pos else "entering"
    return "long" if has_pos else "empty"


def build_daily_trading_summary(
    trade_date: str,
    symbol: str,
    signal: Dict[str, Any],
    final_state: Optional[AgentState],
    portfolio_state: Optional[Dict[str, Any]],
    prev_equity: Optional[float],
) -> Dict[str, Any]:
    """
    Build a row for MemoryDBHelper.upsert_daily_trading_summary().

    返回 dict keys（与 upsert_daily_trading_summary 参数一致）：
    - date, symbol, summary_json
    - market_regime, selected_strategy, expected_behavior
    - actual_return, actual_max_drawdown, positioning, anomaly
    """
    sig_action = str((signal or {}).get("action") or "HOLD").upper()
    entry_type = str((signal or {}).get("entry_type") or "MKT_OPEN").upper()

    research_decision = None
    research_rationale0 = None
    risk_final_decision = None
    trader_plan_json: Dict[str, Any] = {}

    if final_state and isinstance(final_state, dict):
        rs = final_state.get("research_summary") or {}
        if isinstance(rs, dict):
            try:
                raw = rs.get("raw_response") or ""
                rj = extract_json_from_text(raw) if raw else None
                if isinstance(rj, dict):
                    research_decision = rj.get("decision")
                    rationale = rj.get("rationale")
                    if isinstance(rationale, list) and rationale:
                        research_rationale0 = str(rationale[0])
            except Exception:
                pass

        rk = final_state.get("risk_summary") or {}
        if isinstance(rk, dict):
            try:
                fd = (rk.get("final_trade_decision") or "").strip()
                kj = extract_json_from_text(fd) if fd else None
                if isinstance(kj, dict):
                    risk_final_decision = kj.get("final_decision")
            except Exception:
                pass

        trader_plan_str = final_state.get("trader_investment_plan")
        if trader_plan_str:
            try:
                tj = extract_json_from_text(trader_plan_str)
                if isinstance(tj, dict):
                    trader_plan_json = tj
            except Exception:
                trader_plan_json = {}

    # 映射到旧列名（避免修改 DDL）
    market_regime = None
    if research_decision:
        market_regime = str(research_decision).upper()
        if research_rationale0:
            market_regime = f"{market_regime} | {research_rationale0}".strip()

    selected_strategy = f"{sig_action}_{entry_type}"
    expected_behavior = str(trader_plan_json.get("summary") or "").strip() or str((signal or {}).get("reason") or "").strip()

    equity = None
    cash = None
    positions_value = None
    if portfolio_state and isinstance(portfolio_state, dict):
        equity = _safe_float(portfolio_state.get("total_value"))
        cash = _safe_float(portfolio_state.get("cash"))
        positions_value = _safe_float(portfolio_state.get("positions_value"))

    actual_return = _to_pct_return(prev_equity, equity)

    # 单日 max_drawdown：先留空/0，周期级再算更合理
    actual_max_drawdown = 0.0

    anomaly = ""
    if sig_action == "HOLD":
        anomaly = str((signal or {}).get("reason") or "").strip()

    positioning = _summarize_positioning(sig_action, portfolio_state)

    summary_payload = {
        "date": trade_date,
        "symbol": symbol,
        "market_regime": market_regime,
        "selected_strategy": selected_strategy,
        "expected_behavior": expected_behavior,
        "actual_outcome": {
            "equity": equity,
            "cash": cash,
            "positions_value": positions_value,
            "actual_return": actual_return,
        },
        "positioning": positioning,
        "anomaly": anomaly,
        "trader_action": sig_action,
        "risk_decision": risk_final_decision,
        "research_decision": research_decision,
        "signal": signal,
        "trader_plan": trader_plan_json,
        "portfolio_state": portfolio_state,
    }

    return {
        "date": trade_date,
        "symbol": symbol,
        "summary_json": json.dumps(summary_payload, ensure_ascii=False),
        "market_regime": market_regime,
        "selected_strategy": selected_strategy,
        "expected_behavior": expected_behavior,
        "actual_return": actual_return,
        "actual_max_drawdown": actual_max_drawdown,
        "positioning": positioning,
        "anomaly": anomaly,
    }

