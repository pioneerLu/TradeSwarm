"""
Risk 子图

实现 Risk 辩论流程：
- 默认 2 轮：risky → neutral → safe 循环（轮数可由 config/config.yaml graph.max_risk_debate_rounds 配置）
- 最后交由 risk_manager 生成最终决策
"""

from typing import Any, TYPE_CHECKING
from langgraph.graph import StateGraph, END
from langchain_core.language_models import BaseChatModel

if TYPE_CHECKING:
    from langgraph.graph.graph import CompiledGraph
else:
    CompiledGraph = Any

from tradingagents.agents.utils.agentstate.agent_states import AgentState
from tradingagents.agents.pre_open.risk_mgmt.aggresive_debator import create_risky_debator
from tradingagents.agents.pre_open.risk_mgmt.neutral_debator import create_neutral_debator
from tradingagents.agents.pre_open.risk_mgmt.conservative_debator import create_safe_debator
from tradingagents.agents.pre_open.managers.risk_manager.agent import create_risk_manager


def create_risk_subgraph_simple(
    llm: BaseChatModel,
    memory: Any,
    max_debate_rounds: int = 2,
) -> CompiledGraph:
    """
    创建 Risk 子图。

    流程：risky → neutral → safe 循环，每「轮」三者各发言一次；达到轮数后 → risk_manager → END。

    Args:
        llm: LangChain BaseChatModel 实例
        memory: Memory 实例
        max_debate_rounds: 辩论轮数（>=1），默认 2；总发言步数上限为 max_debate_rounds * 3

    Returns:
        编译好的 StateGraph 子图
    """
    rounds = max(1, min(int(max_debate_rounds), 20))
    max_count = rounds * 3

    def should_continue_risk_debate(state: AgentState) -> str:
        risk_summary = state.get("risk_summary")
        if risk_summary is None:
            return "continue"

        debate_state = risk_summary.get("risk_debate_state")
        if debate_state is None:
            return "continue"

        count = debate_state.get("count", 0)
        if count >= max_count:
            return "finish"
        return "continue"

    risky_node = create_risky_debator(llm)
    neutral_node = create_neutral_debator(llm)
    safe_node = create_safe_debator(llm)
    manager_node = create_risk_manager(llm, memory)

    workflow = StateGraph(AgentState)

    workflow.add_node("risky_debator", risky_node)
    workflow.add_node("neutral_debator", neutral_node)
    workflow.add_node("safe_debator", safe_node)
    workflow.add_node("risk_manager", manager_node)

    workflow.set_entry_point("risky_debator")

    workflow.add_edge("risky_debator", "neutral_debator")
    workflow.add_edge("neutral_debator", "safe_debator")

    workflow.add_conditional_edges(
        "safe_debator",
        should_continue_risk_debate,
        {
            "continue": "risky_debator",
            "finish": "risk_manager",
        },
    )

    workflow.add_edge("risk_manager", END)

    return workflow.compile()
