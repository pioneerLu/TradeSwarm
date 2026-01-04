from typing import TypedDict
from langchain_core.messages import AnyMessage


class SocialMediaAnalystState(TypedDict):
    """
    Social Media Analyst Agent 的状态定义
    
    该状态用于存储社交媒体分析 agent 运行过程中的关键数据。
    严格遵循研究型代码规范：不允许使用默认值，确保所有字段都被显式提供。
    
    字段说明:
        company_of_interest: 目标公司的股票代码（如 "AAPL"）
        trade_date: 交易日期，格式为 "YYYY-MM-DD"
        sentiment_report: 情绪分析报告，由本 agent 生成的社交媒体、公众情绪和公司新闻综合分析
        messages: LangChain 消息历史列表，用于存储与 LLM 的交互记录
    """
    company_of_interest: str
    trade_date: str
    sentiment_report: str
    messages: list[AnyMessage]
