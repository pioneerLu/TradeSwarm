"""
Market Analyst Agent 模块

该模块提供市场技术指标分析功能，用于评估股票的当前市场状况。
Agent 会选择并分析金融指标，生成详细的市场分析报告。

主要导出:
    - create_market_analyst: 创建 market analyst agent 节点的工厂函数
    - MarketAnalystState: Agent 状态的类型定义
"""

from .agent import create_market_analyst
from .state import MarketAnalystState

__all__ = [
    "create_market_analyst",
    "MarketAnalystState",
]
