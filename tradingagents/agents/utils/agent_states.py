"""
所有 Agent State 定义

本文件包含系统中所有 State 的定义，包括：
- Analyst 私有 State（节点内部使用）
- Fusion 共享 State（Researcher 和 Risk Manager 共享）
- Manager State（Researcher 和 Risk Manager 内部使用）
- Debate State（辩论状态）
"""
from typing import Annotated, Sequence, TypedDict, Optional, Dict, Any, List, Literal
from datetime import date, timedelta, datetime
from langchain_core.messages import AnyMessage
from langgraph.graph import MessagesState
from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages
from tradingagents.agents.fusion.execution_schemas import ExecutionPlan, ExecutionLog

# ==================== Analyst 私有 State ====================
# 这些 State 仅用于 Analyst 节点内部执行，不进入全局 State

class BaseAnalystState(TypedDict):
    """
    Analyst 基础 State
    
    所有 Analyst 的私有 State 都继承此基础 State。
    该状态仅用于 Analyst 节点内部执行，不进入全局 State。
    报告生成后写入 Memory Controller，State 可丢弃。
    """
    company_of_interest: Annotated[str, "目标股票代码"]
    trade_date: Annotated[str, "交易日期，格式为 'YYYY-MM-DD'"]
    messages: Annotated[list[AnyMessage], "LangChain 消息历史列表"]


class MarketAnalystState(BaseAnalystState):
    """
    Market Analyst 私有 State（分钟级别 - intraday）
    
    继承自 BaseAnalystState，添加 Market Analyst 特有字段。
    """
    trade_timestamp: Annotated[str, "精确时间戳 'YYYY-MM-DD HH:MM:SS'（分钟级，用于 intraday 操作）"]
    market_report: Annotated[str, "市场分析报告（Markdown 格式，临时，生成后写入 Memory）"]


class NewsAnalystState(BaseAnalystState):
    """
    News Analyst 私有 State（天级别 - daily）
    
    继承自 BaseAnalystState，添加 News Analyst 特有字段。
    """
    news_report: Annotated[str, "新闻分析报告（Markdown 格式，临时）"]


class SentimentAnalystState(BaseAnalystState):
    """
    Social Media Analyst 私有 State（天级别 - daily）
    
    继承自 BaseAnalystState，添加 Sentiment Analyst 特有字段。
    """
    sentiment_report: Annotated[str, "情绪分析报告（Markdown 格式，临时）"]


class FundamentalsAnalystState(BaseAnalystState):
    """
    Fundamentals Analyst 私有 State（星期级别 - slow）
    
    继承自 BaseAnalystState，添加 Fundamentals Analyst 特有字段。
    """
    fundamentals_report: Annotated[str, "基本面分析报告（Markdown 格式，临时）"]


# ==================== Memory Summary 结构 ====================

class AnalystMemorySummary(TypedDict):
    """
    单个 Analyst 的 Memory Summary 结构
    
    由 Memory Controller 提供，包含：
    - today_report: 今日生成的报告
    - memory_summary_pre_open: 开盘前长期记忆摘要
    - memory_summary_post_close: 收盘后长期记忆摘要
    
    对于 Market Analyst（频繁更新）：
    - today_report: 最新的市场快照报告
    - memory_summary_pre_open: 开盘前的历史市场趋势摘要
    - memory_summary_post_close: 当日所有快照的聚合摘要
    """
    today_report: Annotated[str, "今日生成的报告"]
    memory_summary_pre_open: Annotated[str, "开盘前长期记忆摘要"]
    memory_summary_post_close: Annotated[str, "收盘后长期记忆摘要"]



# ==================== 子图内部 State ====================
# 这些 State 仅用于 Research/Risk 子图内部，不进入全局 FusionState

class InvestDebateState(TypedDict):
    """
    Researcher 团队辩论状态（仅子图内部使用）
    用于 Researcher 内部的牛熊分析师辩论，完全隔离于全局 FusionState。
    """
    bull_history: Annotated[str, "多头对话历史"]
    bear_history: Annotated[str, "空头对话历史"]
    history: Annotated[str, "整体对话历史"]
    current_response: Annotated[str, "最新回复"]
    judge_decision: Annotated[str, "裁决结果"]
    count: Annotated[int, "当前对话轮次"]


class RiskDebateState(TypedDict):
    """
    Risk Manager 团队辩论状态（仅子图内部使用）
    用于 Risk Manager 内部的风险分析师辩论，完全隔离于全局 FusionState。
    """
    risky_history: Annotated[str, "激进分析师对话历史"]
    safe_history: Annotated[str, "保守分析师对话历史"]
    neutral_history: Annotated[str, "中性分析师对话历史"]
    history: Annotated[str, "整体对话历史"]
    latest_speaker: Annotated[str, "最近发言的分析师"]
    current_risky_response: Annotated[str, "激进分析师最新回复"]
    current_safe_response: Annotated[str, "保守分析师最新回复"]
    current_neutral_response: Annotated[str, "中性分析师最新回复"]
    judge_decision: Annotated[str, "裁决结果"]
    count: Annotated[int, "当前对话轮次"]



class FusionState(MessagesState):
    """
    贯穿全图的全局 State，继承 MessagesState 以保留对话上下文。
    Fusion 节点从四个 Analyst Memory Controller 拉取 AnalystMemorySummary 填充基础字段；
    Research/Risk 子图（Subgraph）内部隔离辩论过程，仅将最终决策写回到此 State；
    Trader 节点消费结构化决策与持仓数据进行下单执行。
    
    设计架构：
    - 辩论过程（bull_history 等）完全隔离在子图内，不污染全局 State
    - 仅保留最终决策与定量交易数据
    - 支持精确风控计算与实盘下单
    """

    # ========== 基础信息 ==========
    company_of_interest: Annotated[str, "目标股票代码"]
    trade_date: Annotated[str, "交易日期 YYYY-MM-DD"]
    trade_timestamp: Annotated[Optional[str], "精确时间戳"]

    # ========== Analyst Memory（只读，由 Fusion 节点填充） ==========
    market_analyst_summary: Annotated[AnalystMemorySummary, "Market Analyst 的 Memory Summary"]
    news_analyst_summary: Annotated[AnalystMemorySummary, "News Analyst 的 Memory Summary"]
    sentiment_analyst_summary: Annotated[AnalystMemorySummary, "Social Media Analyst 的 Memory Summary"]
    fundamentals_analyst_summary: Annotated[AnalystMemorySummary, "Fundamentals Analyst 的 Memory Summary"]

    # ========== 最终决策输出 ==========
    research_summary: Annotated[Optional[Dict[str, Any]], "Research Manager 的最终投资决策（action、理由、置信度）"]
    risk_summary: Annotated[Optional[Dict[str, Any]], "Risk Manager 的风险评估结论（可接纳性、约束条件）"]
    investment_plan: Annotated[Optional[str], "投资计划文本摘要"]
    trader_investment_plan: Annotated[Optional[str], "Trader 生成的最终执行计划"]
    final_trade_decision: Annotated[Optional[str], "最终交易决策"]

    # ========== 账户与持仓数据（这个地方我还在想） ==========
    account_cash: Annotated[float, "账户可用现金（元）"]
    account_total_value: Annotated[float, "账户总权益（现金 + 持仓市值）"]
    current_price: Annotated[float, "当前股票价格"]
    previous_close: Annotated[Optional[float], "前一日收盘价"]
    portfolio_positions: Annotated[Dict[str, Dict[str, Any]], """持仓结构，示例：
        {
            "000001": {
                "quantity": 100,
                "cost_price": 15.5,
                "market_price": 16.2,
                "market_value": 1620.0
            },
            "000002": {...}
        }
    """]
    max_drawdown: Annotated[Optional[float], "账户最大回撤百分比"]

    # ========== 执行记录 ==========
    execution_record: Annotated[Optional[Dict[str, Any]], "下单执行日志与结果"]

    # ========== 混合架构新字段 (Hybrid Architecture) ==========
    market_phase: Annotated[Literal["pre_market", "intraday", "post_market", "sleep"], "当前市场阶段"]
    execution_plan: Annotated[Optional[ExecutionPlan], "盘前生成的结构化执行计划"]
    execution_log: Annotated[Optional[ExecutionLog], "盘中执行后的结果日志"]
    strategy_review: Annotated[Optional[str], "盘后复盘结论"]

