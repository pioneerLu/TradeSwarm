"""
Fundamentals Analyst Agent 模块

该模块提供公司财务基本面和估值分析功能。Fundamentals Analyst 负责评估公司的
盈利能力、成长性、资产负债表健康度、现金流、资本结构和估值水平，
生成详细的基本面分析报告。

主要导出:
    - create_fundamentals_analyst: 创建 fundamentals analyst agent 节点的工厂函数
    - FundamentalsAnalystState: Agent 状态的类型定义
    
工具调用流程:
    1. get_company_info - 获取公司基本信息
    2. get_financial_statements - 获取三大财务报表
    3. get_financial_indicators - 获取财务指标
    4. get_valuation_indicators - 获取估值指标
    5. get_earnings_data - 获取业绩预告/快报（可选）
"""

from .agent import create_fundamentals_analyst
from .state import FundamentalsAnalystState

__all__ = [
    "create_fundamentals_analyst",
    "FundamentalsAnalystState",
]
