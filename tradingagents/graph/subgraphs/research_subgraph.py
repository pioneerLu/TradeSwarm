"""
Research 子图

实现 Research 辩论流程：
- 默认 2 轮辩论：bull → bear → bull → bear（轮数可由 config/config.yaml graph.max_research_debate_rounds 配置）
- 最后交由 research_manager 生成最终决策
"""

from typing import Any, TYPE_CHECKING
from langgraph.graph import StateGraph, END
from langchain_core.language_models import BaseChatModel

from tradingagents.agents.utils.agentstate.agent_states import AgentState
from tradingagents.agents.pre_open.researchers.bull_researcher import create_bull_researcher
from tradingagents.agents.pre_open.researchers.bear_researcher import create_bear_researcher
from tradingagents.agents.pre_open.managers.research_manager.agent import create_research_manager

if TYPE_CHECKING:
    from langgraph.graph.graph import CompiledGraph
else:
    CompiledGraph = Any


def create_research_subgraph_simple(
    llm: BaseChatModel,
    memory: Any,
    max_debate_rounds: int = 2,
) -> CompiledGraph:
    """
    创建 Research 子图。

    流程：bull → bear 循环，每「轮」包含 bull、bear 各一次；达到轮数后 → research_manager → END。

    Args:
        llm: LangChain BaseChatModel 实例
        memory: Memory 实例
        max_debate_rounds: 辩论轮数（>=1），默认 2；总发言步数上限为 max_debate_rounds * 2

    Returns:
        编译好的 StateGraph 子图
    """
    rounds = max(1, min(int(max_debate_rounds), 20))
    max_count = rounds * 2

    def should_continue_debate(state: AgentState) -> str:
        """根据 research_summary.investment_debate_state.count 判断是否进入 manager。"""
        research_summary = state.get("research_summary")
        if research_summary is None:
            return "continue"

        debate_state = research_summary.get("investment_debate_state")
        if debate_state is None:
            return "continue"

        count = debate_state.get("count", 0)
        if count >= max_count:
            return "finish"
        return "continue"

    # 创建节点
    bull_node = create_bull_researcher(llm, memory)
    bear_node = create_bear_researcher(llm, memory)
    manager_node = create_research_manager(llm, memory)

    # 创建子图
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("bull_researcher", bull_node)
    workflow.add_node("bear_researcher", bear_node)
    workflow.add_node("research_manager", manager_node)

    # 设置入口点
    workflow.set_entry_point("bull_researcher")

    # bull → bear（总是执行）
    workflow.add_edge("bull_researcher", "bear_researcher")

    # bear → 判断是否继续辩论
    workflow.add_conditional_edges(
        "bear_researcher",
        should_continue_debate,
        {
            "continue": "bull_researcher",
            "finish": "research_manager",
        },
    )

    workflow.add_edge("research_manager", END)

    return workflow.compile()
