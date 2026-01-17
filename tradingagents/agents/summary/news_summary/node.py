"""
News Summary Node

从数据库读取 News Analyst 的 today_report 和 history_report，填充到 AgentState。
"""

from typing import Callable, Any, Dict
from tradingagents.agents.utils.agent_states import AgentState, AnalystMemorySummary


def create_news_summary_node(data_manager: Any) -> Callable[[AgentState], Dict[str, Any]]:
    """
    创建 News Summary 节点函数
    
    该函数返回一个符合 LangGraph 节点规范的函数，用于从数据库读取 News Analyst 的
    报告摘要并填充到 AgentState。
    
    Args:
        data_manager: 数据管理器实例（用于查询数据库）
        
    Returns:
        news_summary_node: 一个接受 AgentState 并返回更新字典的函数
        
    节点函数返回值:
        dict 包含以下键:
            - news_analyst_summary: AnalystMemorySummary 对象，包含 today_report 和 history_report
    
    实现细节:
        - 从数据库查询 News Analyst 的 today_report（天级别更新）
        - 从数据库查询 history_report（根据 trading_session 决定）
        - News Analyst 是天级别更新（daily）
    """
    
    def news_summary_node(state: AgentState) -> Dict[str, Any]:
        """
        News Summary 节点的执行函数
        
        Args:
            state: 当前的 AgentState
            
        Returns:
            包含 news_analyst_summary 的更新字典
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
            "news_analyst_summary": summary
        }
    
    return news_summary_node


def _query_today_report(data_manager: Any, symbol: str, trade_date: str) -> str:
    """
    从数据库查询 News Analyst 的今日报告
    
    Args:
        data_manager: 数据管理器实例
        symbol: 股票代码（如 '000001'）
        trade_date: 交易日期（如 '2024-01-15'）
    
    Returns:
        今日新闻分析报告
    """
    # TODO: 从数据库查询
    # SQL 示例：
    # SELECT report_content FROM analyst_reports
    # WHERE analyst_type='news' AND symbol=? AND trade_date=?
    # ORDER BY created_at DESC LIMIT 1
    
    # Demo: 返回样例数据
    return f"""# News Analysis Report - {symbol} ({trade_date})

## 今日新闻摘要

### 重要新闻

1. **行业政策利好**
   - 相关部门发布支持政策，利好行业发展
   - 预计将推动相关公司业绩提升

2. **公司公告**
   - 公司发布业绩预告，预计净利润增长 20%
   - 新产品发布获得市场关注

3. **市场动态**
   - 同行业公司表现强劲，板块整体上涨
   - 机构调研频繁，市场关注度提升

## 新闻影响分析

**正面影响**: 
- 政策支持带来长期利好
- 业绩预期改善市场信心

**风险提示**:
- 需关注政策执行细节
- 注意市场情绪波动
"""


def _query_history_report(data_manager: Any, symbol: str, trade_date: str, trading_session: str) -> str:
    """
    从数据库查询 News Analyst 的历史摘要
    
    Args:
        data_manager: 数据管理器实例
        symbol: 股票代码
        trade_date: 交易日期
        trading_session: 交易时段（'pre_open' 或 'post_close'）
    
    Returns:
        历史新闻摘要
    """
    # TODO: 从数据库查询 history_report 字段
    # SQL 示例：
    # SELECT history_report FROM analyst_reports
    # WHERE analyst_type='news' AND symbol=? AND trade_date=?
    # ORDER BY created_at DESC LIMIT 1
    
    # Demo: 返回样例数据
    session_desc = "开盘前" if trading_session == 'pre_open' else "收盘后"
    return f"""# News History Summary - {symbol}

## 近期新闻趋势分析 ({session_desc})

**分析周期**: 过去 7 个交易日

### 新闻热度变化

- **前 3 天**: 新闻数量较少，市场关注度一般
- **近 4 天**: 新闻数量明显增加，政策利好和业绩预期成为焦点

### 主要新闻主题

1. **政策环境**: 行业政策持续优化，支持力度加大
2. **公司动态**: 业绩预告、新产品发布等积极信号
3. **市场情绪**: 机构关注度提升，市场预期改善

### 新闻影响评估

**正面因素**:
- 政策支持带来长期利好预期
- 公司基本面改善信号明显

**需关注**:
- 政策执行效果需持续观察
- 市场情绪可能过度乐观
"""

