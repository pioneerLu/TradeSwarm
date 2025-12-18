from typing import Callable, Any
from pathlib import Path
from jinja2 import Template
from langchain_core.language_models import BaseChatModel

from .state import ResearchManagerState


def create_research_manager(llm: BaseChatModel, memory: Any) -> Callable[[ResearchManagerState], dict[str, Any]]:
    """
    创建 Research Manager agent 节点函数
    
    该函数返回一个符合 LangGraph 节点规范的函数，用于评估投资辩论并生成投资计划。
    Research Manager 作为投资组合经理和辩论促进者，综合牛熊分析师的观点，
    结合历史记忆中的经验教训，做出明确的投资决策（Buy/Sell/Hold）。
    
    Args:
        llm: LangChain BaseChatModel 实例，用于生成投资决策和计划
        memory: FinancialSituationMemory 实例，用于检索过去相似情况的经验教训
        
    Returns:
        research_manager_node: 一个接受 ResearchManagerState 并返回更新字典的函数
        
    节点函数返回值:
        dict 包含以下键:
            - investment_plan: 生成的投资计划文本
            - investment_debate_state: 更新后的投资辩论状态字典
    
    实现细节:
        - 从 prompt.j2 加载 Jinja2 模板并渲染 prompt
        - 使用 memory 检索过去相似情况的经验教训
        - 直接调用 llm.invoke 生成决策（不使用 agent 框架）
        - 保持辩论状态的连续性，仅更新必要字段
    """
    
    def research_manager_node(state: ResearchManagerState) -> dict[str, Any]:
        """
        Research Manager 节点的执行函数
        
        Args:
            state: 当前的 ResearchManagerState
            
        Returns:
            包含 investment_plan 和 investment_debate_state 的更新字典
        """
        # 第一阶段：提取状态信息
        history = state["investment_debate_state"].get("history", "")
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        investment_debate_state = state["investment_debate_state"]
        
        # 第二阶段：构建当前情况描述并检索相关记忆
        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
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
            history=history
        )
        
        # 第四阶段：调用 LLM 生成决策
        response = llm.invoke(prompt)
        
        # 第五阶段：更新投资辩论状态
        new_investment_debate_state = {
            "judge_decision": response.content,
            "history": investment_debate_state.get("history", ""),
            "bear_history": investment_debate_state.get("bear_history", ""),
            "bull_history": investment_debate_state.get("bull_history", ""),
            "current_response": response.content,
            "count": investment_debate_state["count"],
        }
        
        return {
            "investment_debate_state": new_investment_debate_state,
            "investment_plan": response.content,
        }
    
    return research_manager_node
