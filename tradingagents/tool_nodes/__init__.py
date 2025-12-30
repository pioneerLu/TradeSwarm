"""工具节点模块

提供按功能分类的工具节点，每个节点专精于特定领域。
每个节点可以：
1. 作为 LangGraph 的独立节点使用
2. 作为工具集合供 Agent 使用

同时导出所有工具函数，方便直接使用。
"""
# 导出工具节点函数
from .market_node import create_market_tool_node, get_market_tools
from .fundamentals_node import create_fundamentals_tool_node, get_fundamentals_tools
from .news_node import create_news_tool_node, get_news_tools
from .technical_node import create_technical_tool_node, get_technical_tools

# 从 utils 模块导出所有工具函数
from .utils import (
    # 市场数据工具
    get_stock_data,
    # 技术分析工具
    get_indicators,
    # 新闻工具
    get_news,
    get_global_news,
    # 基本面分析工具
    get_company_info,
    get_financial_statements,
    get_financial_indicators,
    get_valuation_indicators,
    get_earnings_data,
)

__all__ = [
    # 市场数据工具节点
    'create_market_tool_node',
    'get_market_tools',
    # 基本面分析工具节点
    'create_fundamentals_tool_node',
    'get_fundamentals_tools',
    # 新闻工具节点
    'create_news_tool_node',
    'get_news_tools',
    # 技术分析工具节点
    'create_technical_tool_node',
    'get_technical_tools',
    # 工具函数
    'get_stock_data',
    'get_indicators',
    'get_news',
    'get_global_news',
    'get_company_info',
    'get_financial_statements',
    'get_financial_indicators',
    'get_valuation_indicators',
    'get_earnings_data',
]

