from typing import Callable, Any
from pathlib import Path
from jinja2 import Template
from langchain_core.language_models import BaseChatModel

from .state import RiskManagerState


def create_risk_manager(llm: BaseChatModel, memory: Any) -> Callable[[RiskManagerState], dict[str, Any]]:
    """
    创建 Risk Manager agent 节点函数
    
    该函数返回一个符合 LangGraph 节点规范的函数，用于评估风险辩论并生成交易员投资计划。
    Risk Manager 作为风险评估促进者，综合激进/保守/中立分析师的观点，
    结合历史记忆中的经验教训，制定明确的交易策略和风险管理参数。
    
    Args:
        llm: LangChain BaseChatModel 实例，用于生成风险评估和交易计划
        memory: FinancialSituationMemory 实例，用于检索过去相似风险评估的经验教训
        
    Returns:
        risk_manager_node: 一个接受 RiskManagerState 并返回更新字典的函数
        
    节点函数返回值:
        dict 包含以下键:
            - trader_investment_plan: 生成的交易员投资计划文本
            - risk_debate_state: 更新后的风险辩论状态字典
    
    实现细节:
        - 从 prompt.j2 加载 Jinja2 模板并渲染 prompt
        - 使用 memory 检索过去相似风险评估的经验教训
        - 直接调用 llm.invoke 生成交易策略（不使用 agent 框架）
        - 保持风险辩论状态的连续性，仅更新必要字段
    """
    
    def risk_manager_node(state: RiskManagerState) -> dict[str, Any]:
        """
        Risk Manager 节点的执行函数
        
        Args:
            state: 当前的 RiskManagerState
            
        Returns:
            包含 trader_investment_plan 和 risk_debate_state 的更新字典
        """
        # 第一阶段：提取状态信息
        history = state["risk_debate_state"].get("history", "")
        investment_plan = state["investment_plan"]
        risk_debate_state = state["risk_debate_state"]
        
        # 第二阶段：构建当前情况描述并检索相关记忆
        # 使用投资计划和风险辩论历史作为情况描述
        curr_situation = f"Investment Plan: {investment_plan}\n\nRisk Debate: {history}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)
        
        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
            past_memory_str += rec["recommendation"] + "\n\n"
        
        # 第三阶段：加载并渲染 prompt 模板
        prompt_path = Path(__file__).parent / "prompt.j2"
        with open(prompt_path, "r", encoding="utf-8") as f:
            template = Template(f.read())
        
        prompt = template.render(
            past_memory_str=past_memory_str,
            investment_plan=investment_plan,
            history=history
        )
        
        # 第四阶段：调用 LLM 生成交易策略
        response = llm.invoke(prompt)
        
        # 第五阶段：更新风险辩论状态
        new_risk_debate_state = {
            "judge_decision": response.content,
            "history": risk_debate_state.get("history", ""),
            "risky_history": risk_debate_state.get("risky_history", ""),
            "safe_history": risk_debate_state.get("safe_history", ""),
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "latest_speaker": risk_debate_state.get("latest_speaker", ""),
            "current_risky_response": risk_debate_state.get("current_risky_response", ""),
            "current_safe_response": risk_debate_state.get("current_safe_response", ""),
            "current_neutral_response": risk_debate_state.get("current_neutral_response", ""),
            "count": risk_debate_state["count"],
        }
        
        return {
            "risk_debate_state": new_risk_debate_state,
            "trader_investment_plan": response.content,
        }
    
    return risk_manager_node
