"""
Fundamentals Summary Node

从数据库读取 Fundamentals Analyst 的 today_report 和 history_report，填充到 AgentState。
"""

from typing import Callable, Any, Dict
from tradingagents.agents.utils.agent_states import AgentState, AnalystMemorySummary


def create_fundamentals_summary_node(data_manager: Any) -> Callable[[AgentState], Dict[str, Any]]:
    """
    创建 Fundamentals Summary 节点函数
    
    该函数返回一个符合 LangGraph 节点规范的函数，用于从数据库读取 Fundamentals Analyst 的
    报告摘要并填充到 AgentState。
    
    Args:
        data_manager: 数据管理器实例（用于查询数据库）
        
    Returns:
        fundamentals_summary_node: 一个接受 AgentState 并返回更新字典的函数
        
    节点函数返回值:
        dict 包含以下键:
            - fundamentals_analyst_summary: AnalystMemorySummary 对象，包含 today_report 和 history_report
    
    实现细节:
        - 从数据库查询 Fundamentals Analyst 的 today_report（周级别更新）
        - 从数据库查询 history_report（根据 trading_session 决定）
        - Fundamentals Analyst 是周级别更新（slow）
    """
    
    def fundamentals_summary_node(state: AgentState) -> Dict[str, Any]:
        """
        Fundamentals Summary 节点的执行函数
        
        Args:
            state: 当前的 AgentState
            
        Returns:
            包含 fundamentals_analyst_summary 的更新字典
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
            "fundamentals_analyst_summary": summary
        }
    
    return fundamentals_summary_node


def _query_today_report(data_manager: Any, symbol: str, trade_date: str) -> str:
    """
    从数据库查询 Fundamentals Analyst 的今日报告
    
    注意：Fundamentals 按周更新，today_report 实际是本周的报告。
    
    Args:
        data_manager: 数据管理器实例
        symbol: 股票代码（如 '000001'）
        trade_date: 交易日期（如 '2024-01-15'）
    
    Returns:
        本周基本面分析报告
    """
    # TODO: 从数据库查询
    # SQL 示例：
    # SELECT report_content FROM analyst_reports
    # WHERE analyst_type='fundamentals' AND symbol=? AND trade_date>=?
    # ORDER BY trade_date DESC LIMIT 1
    
    # Demo: 返回样例数据
    return f"""# Fundamentals Analysis Report - {symbol} ({trade_date})

## 财务指标概览

### 盈利能力

- **ROE (净资产收益率)**: 15.2%
- **ROA (总资产收益率)**: 8.5%
- **净利润率**: 12.3%
- **毛利率**: 35.6%

### 成长性指标

- **营收增长率**: 18.5%
- **净利润增长率**: 22.3%
- **每股收益 (EPS)**: 1.25 元

### 财务健康度

- **资产负债率**: 45.2% (健康)
- **流动比率**: 1.85 (良好)
- **速动比率**: 1.42 (良好)

### 估值指标

- **PE (市盈率)**: 18.5
- **PB (市净率)**: 2.3
- **PEG**: 0.83 (低估)

## 基本面评估

**优势**:
- 盈利能力持续改善
- 财务结构健康，偿债能力强
- 成长性指标表现良好

**关注点**:
- 需关注行业竞争加剧的影响
- 注意成本控制能力
"""


def _query_history_report(data_manager: Any, symbol: str, trade_date: str, trading_session: str) -> str:
    """
    从数据库查询 Fundamentals Analyst 的历史摘要
    
    Args:
        data_manager: 数据管理器实例
        symbol: 股票代码
        trade_date: 交易日期
        trading_session: 交易时段（'pre_open' 或 'post_close'）
    
    Returns:
        历史基本面摘要
    """
    # TODO: 从数据库查询 history_report 字段
    # SQL 示例：
    # SELECT history_report FROM analyst_reports
    # WHERE analyst_type='fundamentals' AND symbol=? AND trade_date=?
    # ORDER BY created_at DESC LIMIT 1
    
    # Demo: 返回样例数据
    session_desc = "开盘前" if trading_session == 'pre_open' else "收盘后"
    return f"""# Fundamentals History Summary - {symbol}

## 近期基本面趋势分析 ({session_desc})

**分析周期**: 过去 4 周

### 财务指标变化趋势

1. **盈利能力**: 持续改善
   - ROE 从 13.5% 提升至 15.2%
   - 净利润率稳步提升

2. **成长性**: 保持强劲
   - 营收增长率维持在 15% 以上
   - 净利润增长加速

3. **财务健康**: 保持稳定
   - 资产负债率控制在合理范围
   - 现金流状况良好

### 基本面评估

**核心优势**:
- 盈利能力和成长性双重驱动
- 财务结构稳健，抗风险能力强
- 行业地位稳固

**长期展望**:
- 基本面持续改善趋势明确
- 估值水平合理，具备投资价值
- 需关注行业周期变化
"""

