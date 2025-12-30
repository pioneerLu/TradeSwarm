"""市场数据工具节点

提供市场数据相关的工具节点和工具集合。
"""
from langgraph.prebuilt import ToolNode
from .utils.market_tools import get_stock_data


def create_market_tool_node():
    """
    创建市场数据工具节点
    
    该节点包含以下工具：
    - get_stock_data: 获取 A 股股票的日线行情数据
    
    Returns:
        ToolNode: LangGraph 工具节点，可在 StateGraph 中使用
        
    Examples:
        >>> from tradingagents.tool_nodes import create_market_tool_node
        >>> graph = StateGraph(AgentState)
        >>> graph.add_node("market_tools", create_market_tool_node())
    """
    tools = [get_stock_data]
    return ToolNode(tools)


def get_market_tools():
    """
    获取市场数据工具列表
    
    用于在 Agent 中直接使用工具，而不是作为独立节点。
    
    Returns:
        list: 市场数据工具列表
        
    Examples:
        >>> from tradingagents.tool_nodes import get_market_tools
        >>> from langchain.agents import create_agent
        >>> tools = get_market_tools()
        >>> agent = create_agent(model=llm, tools=tools)
    """
    return [get_stock_data]

