"""基本面分析工具节点

提供基本面分析相关的工具节点和工具集合。
"""
from langgraph.prebuilt import ToolNode
from .utils.fundamentals_tools import (
    get_company_info,
    get_financial_statements,
    get_financial_indicators,
    get_valuation_indicators,
    get_earnings_data
)


def create_fundamentals_tool_node():
    """
    创建基本面分析工具节点
    
    该节点包含以下工具：
    - get_company_info: 获取公司基本信息
    - get_financial_statements: 获取三大财务报表（利润表、资产负债表、现金流量表）
    - get_financial_indicators: 获取财务指标（ROE、ROA、毛利率、净利率等）
    - get_valuation_indicators: 获取估值指标（PE、PB、PS、股息率等）
    - get_earnings_data: 获取业绩预告、快报数据
    
    Returns:
        ToolNode: LangGraph 工具节点，可在 StateGraph 中使用
        
    Examples:
        >>> from tradingagents.tool_nodes import create_fundamentals_tool_node
        >>> graph = StateGraph(AgentState)
        >>> graph.add_node("fundamentals_tools", create_fundamentals_tool_node())
    """
    tools = [
        get_company_info,
        get_financial_statements,
        get_financial_indicators,
        get_valuation_indicators,
        get_earnings_data
    ]
    return ToolNode(tools)


def get_fundamentals_tools():
    """
    获取基本面分析工具列表
    
    用于在 Agent 中直接使用工具，而不是作为独立节点。
    
    Returns:
        list: 基本面分析工具列表
        
    Examples:
        >>> from tradingagents.tool_nodes import get_fundamentals_tools
        >>> from langchain.agents import create_agent
        >>> tools = get_fundamentals_tools()
        >>> agent = create_agent(model=llm, tools=tools)
    """
    return [
        get_company_info,
        get_financial_statements,
        get_financial_indicators,
        get_valuation_indicators,
        get_earnings_data
    ]

