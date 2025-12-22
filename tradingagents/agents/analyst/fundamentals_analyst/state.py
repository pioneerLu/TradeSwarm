from typing import TypedDict
from langchain_core.messages import AnyMessage


class FundamentalsAnalystState(TypedDict):
    """
    Fundamentals Analyst Agent 的状态定义
    
    该状态用于存储基本面分析 agent 运行过程中的关键数据。
    Fundamentals Analyst 负责评估公司的财务基本面和估值水平，包括盈利能力、成长性、
    资产负债表健康度、现金流、资本结构和估值指标等。
    严格遵循研究型代码规范：不允许使用默认值，确保所有字段都被显式提供。
    
    字段说明:
        company_of_interest: 目标公司的股票代码（如 "000001"）
        trade_date: 交易日期，格式为 "YYYY-MM-DD"
        fundamentals_report: 基本面分析报告，由本 agent 生成的详细财务和估值分析
        messages: LangChain 消息历史列表，用于存储与 LLM 的交互记录
    """
    company_of_interest: str
    trade_date: str
    fundamentals_report: str
    messages: list[AnyMessage]
