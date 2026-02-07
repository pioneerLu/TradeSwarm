"""
策略选择器 Agent

根据 Risk Manager 的决策和分析师报告，选择最适合的交易策略。
仅在 Risk Manager 决策为 BUY 或 SELL 时选择策略，HOLD 时不操作。
"""

from __future__ import annotations

from typing import Callable, Any, Dict, Optional
from langchain_core.language_models import BaseChatModel
import json
import re

from tradingagents.agents.utils.agentstate.agent_states import (
    AgentState,
    StrategySelection,
)
from tradingagents.agents.utils.state_helpers import build_curr_situation_from_summaries
from tradingagents.agents.utils.prompt_loader import load_prompt_template
from tradingagents.agents.utils.json_parser import extract_json_from_text


# 有效的策略类型列表（必须与 trading_sys/strategies/strategy_lib.py 中的 STRATEGY_MAPPING 匹配）
VALID_STRATEGY_TYPES = [
    "trend_following",
    "mean_reversion",
    "momentum_breakout",
    "reversal",
    "range_trading",
    "default_timing",
]


def parse_risk_decision(risk_summary: Optional[Dict[str, Any]]) -> Optional[str]:
    """
    解析 Risk Manager 的决策
    
    Args:
        risk_summary: Risk Manager 的输出
        
    Returns:
        "BUY", "SELL", "HOLD", 或 None
    """
    if not risk_summary:
        return None
    
    final_decision = risk_summary.get("final_trade_decision", "")
    if not final_decision:
        return None
    
    # 尝试从 JSON 中解析
    try:
        # 如果 final_trade_decision 是 JSON 字符串，解析它
        if isinstance(final_decision, str):
            # 尝试提取 JSON
            json_match = re.search(r'\{[^}]+\}', final_decision, re.DOTALL)
            if json_match:
                decision_json = json.loads(json_match.group())
                decision = decision_json.get("final_decision", "").upper()
                if decision in ["BUY", "SELL", "HOLD"]:
                    return decision
    except (json.JSONDecodeError, AttributeError):
        pass
    
    # 如果无法解析 JSON，尝试从文本中提取
    final_decision_upper = final_decision.upper()
    if "BUY" in final_decision_upper or "买入" in final_decision:
        return "BUY"
    elif "SELL" in final_decision_upper or "卖出" in final_decision:
        return "SELL"
    elif "HOLD" in final_decision_upper or "持有" in final_decision:
        return "HOLD"
    
    return None


def create_strategy_selector(
    llm: BaseChatModel, 
    memory: Any
) -> Callable[[AgentState], Dict[str, Any]]:
    """
    创建策略选择器 Agent 节点函数
    
    该函数返回一个符合 LangGraph 节点规范的函数，用于根据风险决策和分析师报告选择交易策略。
    仅在 Risk Manager 决策为 BUY 或 SELL 时选择策略，HOLD 时不操作。
    
    Args:
        llm: LangChain BaseChatModel 实例，用于生成策略选择
        memory: FinancialSituationMemory 实例（可选，用于检索历史经验）
        
    Returns:
        strategy_selector_node: 一个接受 AgentState 并返回更新字典的函数
        
    节点函数返回值:
        dict 包含以下键:
            - strategy_selection: StrategySelection 对象（如果决策为 BUY/SELL）
            - 如果决策为 HOLD，则不更新 strategy_selection
    """
    
    def strategy_selector_node(state: AgentState) -> Dict[str, Any]:
        """
        策略选择器节点的执行函数
        
        Args:
            state: 当前的 AgentState
            
        Returns:
            包含 strategy_selection 的更新字典（如果决策为 BUY/SELL）
        """
        company_name = state.get("company_of_interest", "")
        trade_date = state.get("trade_date", "")
        
        # 1. 读取 Risk Manager 的决策
        risk_summary: Optional[Dict[str, Any]] = state.get("risk_summary")
        risk_decision = parse_risk_decision(risk_summary)
        
        # 2. 判断是否需要选择策略
        # 如果决策为 HOLD 或无法解析，不选择策略
        if risk_decision not in ["BUY", "SELL"]:
            # 返回空的 strategy_selection 或 None，表示不选择策略
            return {
                "strategy_selection": None,
            }
        
        # 3. 读取分析师报告
        market_summary = state.get("market_analyst_summary", {})
        news_summary = state.get("news_analyst_summary", {})
        sentiment_summary = state.get("sentiment_analyst_summary", {})
        fundamentals_summary = state.get("fundamentals_analyst_summary", {})
        
        market_report = market_summary.get("today_report", "") if isinstance(market_summary, dict) else ""
        news_report = news_summary.get("today_report", "") if isinstance(news_summary, dict) else ""
        sentiment_report = sentiment_summary.get("today_report", "") if isinstance(sentiment_summary, dict) else ""
        fundamentals_report = fundamentals_summary.get("today_report", "") if isinstance(fundamentals_summary, dict) else ""
        
        # 4. 读取 Research Manager 和 Risk Manager 的输出
        research_summary: Optional[Dict[str, Any]] = state.get("research_summary")
        investment_plan = (
            research_summary.get("investment_plan", "") if research_summary else ""
        )
        
        final_trade_decision = (
            risk_summary.get("final_trade_decision", "") if risk_summary else ""
        )
        
        # 5. 构建当前情境（用于检索历史记忆，可选）
        curr_situation = build_curr_situation_from_summaries(state)
        past_memories = memory.get_memories(curr_situation, n_matches=2) if memory else []
        
        past_memory_str = ""
        if past_memories:
            for rec in past_memories:
                past_memory_str += rec.get("recommendation", "") + "\n\n"
        else:
            past_memory_str = "无历史记忆。"
        
        # 6. 加载并渲染 prompt 模板
        prompt = load_prompt_template(
            agent_type="managers",
            agent_name="strategy_selector",
            context={
                "company_name": company_name,
                "trade_date": trade_date,
                "risk_decision": risk_decision,
                "final_trade_decision": final_trade_decision,
                "investment_plan": investment_plan,
                "market_report": market_report,
                "news_report": news_report,
                "sentiment_report": sentiment_report,
                "fundamentals_report": fundamentals_report,
                "past_memory_str": past_memory_str,
            },
        )
        
        # 7. 调用 LLM 生成策略选择
        response = llm.invoke(prompt)
        content: str = getattr(response, "content", str(response))
        
        # 8. 解析 JSON 输出
        try:
            # 提取 JSON
            json_dict = extract_json_from_text(content)
            if json_dict is None:
                raise ValueError("无法从输出中提取 JSON")
            strategy_data = json_dict
            
            # 验证策略类型
            strategy_type = strategy_data.get("strategy_type", "").lower()
            if strategy_type not in VALID_STRATEGY_TYPES:
                # 降级到默认策略
                strategy_type = "default_timing"
                strategy_data["strategy_type"] = strategy_type
                strategy_data["reasoning"] = (
                    strategy_data.get("reasoning", "") + 
                    f"\n\n[注意：原始策略类型无效，已降级到 default_timing]"
                )
            
            # 构建 StrategySelection 对象
            strategy_selection: StrategySelection = {
                "strategy_type": strategy_type,  # type: ignore
                "reasoning": strategy_data.get("reasoning", ""),
                "strategy_analysis": strategy_data.get("strategy_analysis", ""),
                "risk_adjustment": strategy_data.get("risk_adjustment"),
                "confidence": float(strategy_data.get("confidence", 0.5)),
                "alternative_strategies": strategy_data.get("alternative_strategies"),
            }
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # 解析失败，使用默认策略
            strategy_selection: StrategySelection = {
                "strategy_type": "default_timing",  # type: ignore
                "reasoning": f"策略选择解析失败: {str(e)}，使用默认策略。",
                "strategy_analysis": "由于无法解析策略选择结果，使用默认择时策略。",
                "risk_adjustment": None,
                "confidence": 0.3,
                "alternative_strategies": None,
            }
        
        return {
            "strategy_selection": strategy_selection,
        }
    
    return strategy_selector_node

