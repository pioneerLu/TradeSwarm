"""技术分析工具节点

提供技术分析相关的工具节点和工具集合。
"""
from langgraph.prebuilt import ToolNode
from .utils.technical_tools import get_indicators


def create_technical_tool_node():
    """
    创建技术分析工具节点
    
    该节点包含以下工具：
    - get_indicators: 获取 A 股股票的技术指标数据（MA、RSI、MACD、BOLL、KDJ、OBV等）
    
    Returns:
        ToolNode: LangGraph 工具节点，可在 StateGraph 中使用
        
    Examples:
        >>> from tradingagents.tool_nodes import create_technical_tool_node
        >>> graph = StateGraph(AgentState)
        >>> graph.add_node("technical_tools", create_technical_tool_node())
    """
    tools = [get_indicators]
    return ToolNode(tools)


def get_technical_tools():
    """
    获取技术分析工具列表
    
    用于在 Agent 中直接使用工具，而不是作为独立节点。
    
    Returns:
        list: 技术分析工具列表
        
    Examples:
        >>> from tradingagents.tool_nodes import get_technical_tools
        >>> from langchain.agents import create_agent
        >>> tools = get_technical_tools()
        >>> agent = create_agent(model=llm, tools=tools)
    """
    return [get_indicators]

