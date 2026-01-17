"""
Sentiment Summary Node

从数据库读取 Social Media Analyst 的 today_report 和 history_report，填充到 AgentState。
"""

from typing import Callable, Any, Dict
from tradingagents.agents.utils.agent_states import AgentState, AnalystMemorySummary


def create_sentiment_summary_node(data_manager: Any) -> Callable[[AgentState], Dict[str, Any]]:
    """
    创建 Sentiment Summary 节点函数
    
    该函数返回一个符合 LangGraph 节点规范的函数，用于从数据库读取 Sentiment Analyst 的
    报告摘要并填充到 AgentState。
    
    Args:
        data_manager: 数据管理器实例（用于查询数据库）
        
    Returns:
        sentiment_summary_node: 一个接受 AgentState 并返回更新字典的函数
        
    节点函数返回值:
        dict 包含以下键:
            - sentiment_analyst_summary: AnalystMemorySummary 对象，包含 today_report 和 history_report
    
    实现细节:
        - 从数据库查询 Sentiment Analyst 的 today_report（天级别更新）
        - 从数据库查询 history_report（根据 trading_session 决定）
        - Sentiment Analyst 是天级别更新（daily）
    """
    
    def sentiment_summary_node(state: AgentState) -> Dict[str, Any]:
        """
        Sentiment Summary 节点的执行函数
        
        Args:
            state: 当前的 AgentState
            
        Returns:
            包含 sentiment_analyst_summary 的更新字典
        """
        # 第一阶段：提取参数
        symbol = state["company_of_interest"]
        trade_date = state["trade_date"]
        trading_session = state.get("trading_session", "post_close")
        
        # 第二阶段：查询数据库
        today_report = _query_today_report(data_manager, symbol, trade_date)
        history_report = _query_history_report(data_manager, symbol, trade_date, trading_session)
        
        # 第三阶段：构建 AnalystMemorySummary
        summary: AnalystMemorySummary = {
            "today_report": today_report,
            "history_report": history_report
        }
        
        return {
            "sentiment_analyst_summary": summary
        }
    
    return sentiment_summary_node


def _query_today_report(data_manager: Any, symbol: str, trade_date: str) -> str:
    """
    从数据库查询 Sentiment Analyst 的今日报告
    
    Args:
        data_manager: 数据管理器实例
        symbol: 股票代码（如 '000001'）
        trade_date: 交易日期（如 '2024-01-15'）
    
    Returns:
        今日情绪分析报告
    """
    # TODO: 从数据库查询
    # SQL 示例：
    # SELECT report_content FROM analyst_reports
    # WHERE analyst_type='sentiment' AND symbol=? AND trade_date=?
    # ORDER BY created_at DESC LIMIT 1
    
    # Demo: 返回样例数据
    return f"""# Social Media Sentiment Analysis Report - {symbol} ({trade_date})

## 今日情绪概览

**整体情绪**: 偏乐观 (Sentiment Score: 0.65)

### 情绪分布

- **正面情绪**: 65%
- **中性情绪**: 25%
- **负面情绪**: 10%

### 主要讨论话题

1. **业绩预期**
   - 用户对业绩预告反应积极
   - 多数观点认为公司前景良好

2. **市场表现**
   - 对近期股价上涨表示认可
   - 部分用户关注回调风险

3. **行业动态**
   - 对行业政策利好表示期待
   - 关注同行业公司表现

## 情绪指标

- **情绪强度**: 中等偏高
- **讨论热度**: 较高
- **意见分歧**: 较小（多数偏乐观）
"""


def _query_history_report(data_manager: Any, symbol: str, trade_date: str, trading_session: str) -> str:
    """
    从数据库查询 Sentiment Analyst 的历史摘要
    
    Args:
        data_manager: 数据管理器实例
        symbol: 股票代码
        trade_date: 交易日期
        trading_session: 交易时段（'pre_open' 或 'post_close'）
    
    Returns:
        历史情绪摘要
    """
    # TODO: 从数据库查询 history_report 字段
    # SQL 示例：
    # SELECT history_report FROM analyst_reports
    # WHERE analyst_type='sentiment' AND symbol=? AND trade_date=?
    # ORDER BY created_at DESC LIMIT 1
    
    # Demo: 返回样例数据
    session_desc = "开盘前" if trading_session == 'pre_open' else "收盘后"
    return f"""# Sentiment History Summary - {symbol}

## 近期情绪趋势分析 ({session_desc})

**分析周期**: 过去 7 个交易日

### 情绪变化趋势

- **前 3 天**: 情绪中性偏乐观，讨论热度一般
- **近 4 天**: 情绪明显转暖，正面情绪占比提升至 65%

### 情绪驱动因素

1. **业绩预期改善**: 用户对公司业绩预期提升
2. **政策利好**: 行业政策支持带来正面情绪
3. **市场表现**: 股价上涨增强市场信心

### 情绪风险评估

**正面信号**:
- 情绪持续改善，市场信心增强
- 讨论热度提升，关注度增加

**需关注**:
- 情绪可能过度乐观，需警惕回调风险
- 注意负面情绪的变化趋势
"""

