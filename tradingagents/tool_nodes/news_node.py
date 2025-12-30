"""新闻工具节点

提供新闻相关的工具节点和工具集合。
"""
from langgraph.prebuilt import ToolNode
from .utils.news_tools import get_news, get_global_news


def create_news_tool_node():
    """
    创建新闻工具节点
    
    该节点包含以下工具：
    - get_news: 获取 A 股股票相关的新闻和公告信息
    - get_global_news: 获取宏观经济新闻和全球市场新闻
    
    Returns:
        ToolNode: LangGraph 工具节点，可在 StateGraph 中使用
        
    Examples:
        >>> from tradingagents.tool_nodes import create_news_tool_node
        >>> graph = StateGraph(AgentState)
        >>> graph.add_node("news_tools", create_news_tool_node())
    """
    tools = [get_news, get_global_news]
    return ToolNode(tools)


def get_news_tools():
    """
    获取新闻工具列表
    
    用于在 Agent 中直接使用工具，而不是作为独立节点。
    
    Returns:
        list: 新闻工具列表
        
    Examples:
        >>> from tradingagents.tool_nodes import get_news_tools
        >>> from langchain.agents import create_agent
        >>> tools = get_news_tools()
        >>> agent = create_agent(model=llm, tools=tools)
    """
    return [get_news, get_global_news]

