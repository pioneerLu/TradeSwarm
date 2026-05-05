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

VALID_REGIMES = {"strong_uptrend", "range_bound", "downtrend", "high_vol_uncertain"}
VALID_SKILLS = {f"{name}_skill" for name in VALID_REGIMES}


def _get_close_price(data_adapter: DataAdapter, symbol: str, trade_date: str) -> Optional[float]:
    try:
        px = data_adapter.get_price(symbol, trade_date, "close")
        return float(px) if px is not None else None
    except Exception:
        return None


def _limit_offset_pct(close_px: Optional[float], limit_px: Optional[float]) -> Optional[float]:
    if close_px is None or limit_px is None or close_px <= 0 or limit_px <= 0:
        return None
    return abs(close_px - limit_px) / close_px


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


def _normalize_regime(value: Any) -> Optional[str]:
    v = str(value or "").strip().lower()
    return v if v in VALID_REGIMES else None


def _normalize_skill(value: Any, regime: Optional[str] = None) -> Optional[str]:
    v = str(value or "").strip().lower()
    if v in VALID_SKILLS:
        return v
    if regime in VALID_REGIMES:
        return f"{regime}_skill"
    return None


def _clip_confidence(value: Any) -> Optional[float]:
    v = _safe_float(value)
    if v is None:
        return None
    return max(0.0, min(1.0, v))


def _normalize_evidence(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()][:5]
    if isinstance(value, str) and value.strip():
        return [value.strip()][:1]
    return []


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


def _maybe_extract_pct_hint(text: str) -> Optional[float]:
    """
    Heuristic: extract a likely target position hint from natural language.
    Examples: '70%仓位' -> 0.7, '0.6~0.8' -> picks first number 0.6.
    """
    if not text:
        return None
    t = str(text)
    # Prefer explicit percent like '70%'
    import re

    m = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%", t)
    if m:
        try:
            v = float(m.group(1)) / 100.0
            return v if 0.0 <= v <= 1.0 else None
        except Exception:
            return None
    # Fallback: decimal like 0.6 / 0.7
    m2 = re.search(r"\b(0(?:\.\d+)?|1(?:\.0+)?)\b", t)
    if m2:
        try:
            v = float(m2.group(1))
            return v if 0.0 <= v <= 1.0 else None
        except Exception:
            return None
    return None


def _extract_position_info(state: AgentState) -> Dict[str, Any]:
    """Extract position info from state for guard rules."""
    cp = state.get("current_position")
    ps = state.get("portfolio_state")
    if not cp:
        return {"has_position": False, "shares": 0, "entry_price": 0, "pnl_pct": 0, "current_weight": 0}
    shares = float(cp.get("shares") or 0)
    entry_price = float(cp.get("entry_price") or 0)
    pnl_pct = float(cp.get("pnl_pct") or 0)
    market_value = shares * float(cp.get("current_price") or 0)
    total_value = float((ps or {}).get("total_value") or 0)
    current_weight = market_value / total_value if total_value > 0 else 0
    return {
        "has_position": shares > 1e-9,
        "shares": shares,
        "entry_price": entry_price,
        "pnl_pct": pnl_pct,
        "current_weight": current_weight,
    }


def resolve_signal(
    state: AgentState,
    is_holding: bool,
    data_adapter: DataAdapter,
) -> Dict[str, Any]:
    """
    从 Pre-Open 的 state 解析出最终交易信号。

    Uses full position info from state when available (interleaved backtest mode)
    and falls back to the simple is_holding flag (legacy batch mode).

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
        "market_regime": None,
        "selected_skill": None,
        "regime_confidence": None,
        "regime_evidence": [],
        "skill_router_mode": None,
        "forced_selected_skill": None,
        "reflection_market_regime": None,
        "reflection_selected_skill": None,
        "reflection_confidence": None,
        "reflection_evidence": [],
    }

    if not symbol or not trade_date:
        return default_hold

    next_trading_day = data_adapter.get_next_trading_day(trade_date)
    pos_info = _extract_position_info(state)
    has_position = pos_info["has_position"] or is_holding
    close_px = _get_close_price(data_adapter, symbol, trade_date)

    # Trader output (primary source)
    trader_json = _parse_trader_plan(state.get("trader_investment_plan"))
    skill_ctx = state.get("strategy_skill_context")
    skill_ctx = skill_ctx if isinstance(skill_ctx, dict) else {}
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

    # Risk Manager output (constraint layer)
    risk_json = _parse_risk_decision(state.get("risk_summary"))
    risk_action = str(risk_json.get("final_decision", "")).upper()
    risk_position_size = _safe_float(risk_json.get("position_size"))
    risk_stop_loss = risk_json.get("stop_loss")
    risk_take_profit = risk_json.get("take_profit")

    # Risk Manager can correct Trader's regime/skill; fallback to Trader.
    market_regime = _normalize_regime(risk_json.get("market_regime")) or _normalize_regime(
        trader_json.get("market_regime")
    )
    forced_selected_skill = _normalize_skill(skill_ctx.get("forced_selected_skill"))
    selected_skill = (
        _normalize_skill(risk_json.get("selected_skill"), market_regime)
        or _normalize_skill(trader_json.get("selected_skill"), market_regime)
        or forced_selected_skill
    )
    regime_confidence = _clip_confidence(risk_json.get("regime_confidence"))
    if regime_confidence is None:
        regime_confidence = _clip_confidence(trader_json.get("regime_confidence"))
    regime_evidence = _normalize_evidence(risk_json.get("regime_evidence")) or _normalize_evidence(
        trader_json.get("regime_evidence")
    )
    regime_meta = {
        "market_regime": market_regime,
        "selected_skill": selected_skill,
        "regime_confidence": regime_confidence,
        "regime_evidence": regime_evidence,
        "skill_router_mode": skill_ctx.get("skill_router_mode"),
        "forced_selected_skill": forced_selected_skill,
        "reflection_market_regime": _normalize_regime(skill_ctx.get("reflection_market_regime")),
        "reflection_selected_skill": _normalize_skill(
            skill_ctx.get("reflection_selected_skill"),
            _normalize_regime(skill_ctx.get("reflection_market_regime")),
        ),
        "reflection_confidence": _clip_confidence(skill_ctx.get("reflection_confidence")),
        "reflection_evidence": _normalize_evidence(skill_ctx.get("reflection_evidence")),
    }

    merged_action = risk_action if risk_action in {"BUY", "SELL", "HOLD"} else trader_action
    if merged_action not in {"BUY", "SELL", "HOLD"}:
        merged_action = "HOLD"

    if merged_action == "HOLD":
        return {
            **default_hold,
            **regime_meta,
            "execution_date": next_trading_day,
            "reason": "Risk/Trader 决策为 HOLD",
        }

    base_target_pct = _clip_pct(trader_target_pct, default=0.5 if merged_action == "BUY" else 0.0)
    risk_cap_pct = _clip_pct(risk_position_size, default=base_target_pct)
    final_target_pct = min(base_target_pct, risk_cap_pct)
    if merged_action == "SELL":
        final_target_pct = 0.0

    # Guard: duplicate BUY at same target -> HOLD
    if merged_action == "BUY" and has_position:
        current_weight = pos_info["current_weight"]
        delta = final_target_pct - current_weight
        # 抑制微小加仓（避免频繁发小单）
        if delta < 0.05:
            return {
                **default_hold,
                **regime_meta,
                "execution_date": next_trading_day,
                "reason": f"已持仓 {current_weight:.1%}，目标 {final_target_pct:.1%} 无显著增量，HOLD",
            }
        # QuantConnect 的 SetHoldings/CalculateOrderQuantity 需要目标总仓位，
        # delta 只用于判断是否值得加仓，不能作为最终 target_pct 传出。

    # Guard: SELL with no position -> HOLD
    if merged_action == "SELL" and not has_position:
        return {
            **default_hold,
            **regime_meta,
            "execution_date": next_trading_day,
            "reason": "当前未持仓，忽略 SELL",
        }

    entry_type = trader_entry_type if trader_entry_type in {"MKT_OPEN", "LIMIT", "STOP"} else "MKT_OPEN"
    entry_price = trader_entry_price

    # Guard: LIMIT 偏离过大自动升级为 MKT_OPEN（避免长期挂单打不到）
    if merged_action in {"BUY", "SELL"} and entry_type == "LIMIT":
        off = _limit_offset_pct(close_px, entry_price)
        if off is not None and off > 0.02:
            entry_type = "MKT_OPEN"
            entry_price = None
            trader_summary = (trader_summary + "；" if trader_summary else "") + f"LIMIT 偏离 {off:.1%}，自动改 MKT_OPEN"

    # 提示 QC 侧在执行前撤销旧挂单，避免 pending 堆积/占用资金预留
    cancel_pending_orders = True if merged_action in {"BUY", "SELL"} else False

    # Consistency hint: if summary implies a target_pct far from JSON, append a note.
    hint = _maybe_extract_pct_hint(trader_summary)
    if hint is not None:
        try:
            if abs(float(hint) - float(final_target_pct)) > 0.15:
                trader_summary = (
                    (trader_summary + "；" if trader_summary else "")
                    + f"注意：文本仓位提示≈{hint:.0%} 与 target_pct={final_target_pct:.0%} 不一致，以 target_pct 为准"
                )
        except Exception:
            pass

    return {
        "action": merged_action,
        "target_pct": final_target_pct,
        "stop_loss": risk_stop_loss or risk_controls.get("stop_loss_pct"),
        "take_profit": risk_take_profit or risk_controls.get("take_profit_pct"),
        "entry_type": entry_type,
        "entry_price": entry_price,
        "reason": trader_summary or "由 Trader 生成可执行计划，并由 Risk 进行约束",
        "is_exploratory": False,
        "execution_date": next_trading_day,
        "cancel_pending_orders": cancel_pending_orders,
        **regime_meta,
    }
