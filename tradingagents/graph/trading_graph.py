"""
主交易图

完整的交易决策流程：
1. Summary Nodes（并行）：market, news, sentiment, fundamentals
2. Research 子图：bull/bear 辩论 → research_manager
3. Trader：生成可执行交易计划（方向、仓位、买点/入场方式、风控）
4. Risk 子图：risky/neutral/safe 辩论 → risk_manager（最终风险评估）
6. 结束
"""

from typing import Any, TYPE_CHECKING, Optional
from langgraph.graph import StateGraph, END
from langchain_core.language_models import BaseChatModel

if TYPE_CHECKING:
    from langgraph.pregel import Pregel as CompiledGraph
else:
    CompiledGraph = Any

from tradingagents.agents.utils.agentstate.agent_states import AgentState
from tradingagents.agents.pre_open.summary import create_summary_loader_node
from tradingagents.agents.pre_open.trader.trader import create_trader
from tradingagents.graph.subgraphs.research_subgraph import create_research_subgraph_simple
from tradingagents.graph.subgraphs.risk_subgraph import create_risk_subgraph_simple
from tradingagents.graph.utils import load_graph_debate_rounds


def create_trading_graph(
    llm: BaseChatModel,
    memory: Any,
    data_manager: Any = None,
    max_research_debate_rounds: Optional[int] = None,
    max_risk_debate_rounds: Optional[int] = None,
) -> CompiledGraph:
    """
    创建完整的交易决策图。

    Args:
        llm: LangChain BaseChatModel 实例
        memory: Memory 实例（如 HybridMemory：Chroma + cycle_reflections 兜底）
        data_manager: MemoryDBHelper 数据库连接
        max_research_debate_rounds: 研究侧辩论轮数；默认从 config/config.yaml 的 graph.max_research_debate_rounds 读取
        max_risk_debate_rounds: 风险侧辩论轮数；默认从 graph.max_risk_debate_rounds 读取

    Returns:
        编译好的 StateGraph
    """
    summary_loader_node = create_summary_loader_node(data_manager)
    
    # 创建 Trader 节点
    trader_node = create_trader(llm, memory)
    
    dr, rr = load_graph_debate_rounds()
    if max_research_debate_rounds is None:
        max_research_debate_rounds = dr
    if max_risk_debate_rounds is None:
        max_risk_debate_rounds = rr

    research_subgraph = create_research_subgraph_simple(
        llm, memory, max_debate_rounds=max_research_debate_rounds
    )
    risk_subgraph = create_risk_subgraph_simple(
        llm, memory, max_debate_rounds=max_risk_debate_rounds
    )
    
    # 创建主图
    workflow = StateGraph(AgentState)
    
    workflow.add_node("summary_loader", summary_loader_node)
    
    # 添加 Trader 节点
    workflow.add_node("trader", trader_node)
    
    workflow.add_node("research_subgraph", research_subgraph)
    workflow.add_node("risk_subgraph", risk_subgraph)
    
    workflow.set_entry_point("summary_loader")
    workflow.add_edge("summary_loader", "research_subgraph")
    
    # Research 子图完成后进入 Trader
    workflow.add_edge("research_subgraph", "trader")
    
    # Trader 完成后进入 Risk 子图（最终风险评估）
    workflow.add_edge("trader", "risk_subgraph")
    
    # Risk 子图完成后结束
    workflow.add_edge("risk_subgraph", END)
    
    return workflow.compile()
