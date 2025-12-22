"""
News Analyst Agent 模块

该模块提供新闻和宏观经济分析功能，用于分析过去7天的全球和公司特定新闻事件。
Agent 会生成详细的新闻分析报告，评估对投资决策的潜在影响。

主要导出:
    - create_news_analyst: 创建 news analyst agent 节点的工厂函数
    - NewsAnalystState: Agent 状态的类型定义
"""

from .agent import create_news_analyst
from .state import NewsAnalystState

__all__ = [
    "create_news_analyst",
    "NewsAnalystState",
]
