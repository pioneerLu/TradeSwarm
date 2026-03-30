#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
信号解析器。
从 Pre-Open 产出的 AgentState 中解析出 QuantConnect 可执行信号。

"""

from __future__ import annotations

from typing import Any, Dict, Optional

from tradingagents.agents.utils.agentstate.agent_states import AgentState
from tradingagents.agents.utils.json_parser import extract_json_from_text
from tradingagents.core.data_adapter import DataAdapter


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _clip_pct(value: Optional[float], default: float) -> float:
    if value is None:
        return default
    return max(0.0, min(1.0, value))


def _parse_trader_plan(trader_plan_str: Optional[str]) -> Dict[str, Any]:
    if not trader_plan_str:
        return {}
    try:
        obj = extract_json_from_text(trader_plan_str)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _parse_risk_decision(risk_summary: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not risk_summary:
        return {}
    final_decision_str = risk_summary.get("final_trade_decision", "")
    if not final_decision_str:
        return {}
    try:
        obj = extract_json_from_text(final_decision_str)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def resolve_signal(
    state: AgentState,
    is_holding: bool,
    data_adapter: DataAdapter,
) -> Dict[str, Any]:
    """
    从 Pre-Open 的 state 解析出最终交易信号。

    Args:
        state: Pre-Open 图输出的 AgentState
        is_holding: 当前是否已持有该标的
        data_adapter: 数据适配器（用于计算下一个交易日）

    Returns:
        标准化信号字典，包含 action、target_pct、execution_date、entry_type、entry_price、reason 等字段。
    """
    symbol = state.get("company_of_interest", "")
    trade_date = state.get("trade_date", "")

    default_hold = {
        "action": "HOLD",
        "target_pct": 0.0,
        "stop_loss": None,
        "take_profit": None,
        "entry_type": "MKT_OPEN",
        "entry_price": None,
        "reason": "",
        "is_exploratory": False,
        "execution_date": None,
    }

    if not symbol or not trade_date:
        return default_hold

    # 1) 获取 T+1 执行日
    next_trading_day = data_adapter.get_next_trading_day(trade_date)

    # 2) Trader 直接输出（主来源）
    trader_json = _parse_trader_plan(state.get("trader_investment_plan"))
    trader_action = str(trader_json.get("action", "HOLD")).upper()
    trader_target_pct = _safe_float(trader_json.get("target_pct"))
    trader_entry_type = str(trader_json.get("entry_type", "MKT_OPEN")).upper()
    trader_entry_price = _safe_float(trader_json.get("entry_price"))
    trader_summary = str(trader_json.get("summary", "") or "")
    risk_controls = (
        trader_json.get("risk_controls", {})
        if isinstance(trader_json.get("risk_controls"), dict)
        else {}
    )

    # 3) Risk Manager 输出（约束层）
    risk_json = _parse_risk_decision(state.get("risk_summary"))
    risk_action = str(risk_json.get("final_decision", "")).upper()
    risk_position_size = _safe_float(risk_json.get("position_size"))
    risk_stop_loss = risk_json.get("stop_loss")
    risk_take_profit = risk_json.get("take_profit")

    # 4) 动作融合：Risk 明确时优先，否则使用 Trader
    merged_action = risk_action if risk_action in {"BUY", "SELL", "HOLD"} else trader_action
    if merged_action not in {"BUY", "SELL", "HOLD"}:
        merged_action = "HOLD"

    if merged_action == "HOLD":
        return {
            **default_hold,
            "execution_date": next_trading_day,
            "reason": "Risk/Trader 决策为 HOLD",
        }

    # 5) 仓位融合：Risk 仅做上限约束，不放大 Trader 仓位
    base_target_pct = _clip_pct(trader_target_pct, default=0.5 if merged_action == "BUY" else 0.0)
    risk_cap_pct = _clip_pct(risk_position_size, default=base_target_pct)
    final_target_pct = min(base_target_pct, risk_cap_pct)
    if merged_action == "SELL":
        final_target_pct = 0.0

    # 6) 基础有效性约束
    if merged_action == "BUY" and is_holding and final_target_pct <= 0:
        return {
            **default_hold,
            "execution_date": next_trading_day,
            "reason": "已持仓且目标仓位无增量，忽略 BUY",
        }
    if merged_action == "SELL" and not is_holding:
        return {
            **default_hold,
            "execution_date": next_trading_day,
            "reason": "当前未持仓，忽略 SELL",
        }

    return {
        "action": merged_action,
        "target_pct": final_target_pct,
        "stop_loss": risk_stop_loss or risk_controls.get("stop_loss_pct"),
        "take_profit": risk_take_profit or risk_controls.get("take_profit_pct"),
        "entry_type": trader_entry_type if trader_entry_type in {"MKT_OPEN", "LIMIT", "STOP"} else "MKT_OPEN",
        "entry_price": trader_entry_price,
        "reason": trader_summary or "由 Trader 生成可执行计划，并由 Risk 进行约束",
        "is_exploratory": False,
        "execution_date": next_trading_day,
    }
