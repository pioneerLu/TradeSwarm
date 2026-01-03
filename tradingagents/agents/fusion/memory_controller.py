"""
Memory Controller 接口定义

每个 Analyst 对应一个 Memory Controller，负责：
1. 维护该 Analyst 的历史报告
2. 使用 LLM 按时间段生成记忆摘要（开盘前/收盘后）
3. 对外暴露统一的 memory_summary 接口

特殊处理：
- Market Analyst 需要频繁更新（分钟级），today_report 始终是最新快照
- News/Sentiment 在开盘前（9:30前）更新，用于指导策略
- Fundamentals 按周更新
"""
from typing import Protocol, Optional, List, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path
from jinja2 import Template
from langchain_core.language_models import BaseChatModel

from tradingagents.agents.utils.agent_states import AnalystMemorySummary


class IMemoryController(Protocol):
    """
    Memory Controller 接口协议
    
    所有 Analyst 的 Memory Controller 必须实现此接口
    """
    
    def save_today_report(
        self,
        symbol: str,
        trade_date: str,
        report_content: str,
        trade_timestamp: Optional[str] = None  # 用于 Market 的分钟级时间戳
    ) -> bool:
        """
        保存今日报告
        
        Args:
            symbol: 股票代码
            trade_date: 交易日期 YYYY-MM-DD
            report_content: 报告内容（Markdown）
            trade_timestamp: 精确时间戳（Market Analyst 需要，格式 "YYYY-MM-DD HH:MM:SS"）
        
        Returns:
            是否保存成功
        """
        ...
    
    def get_memory_summary(
        self,
        symbol: str,
        trade_date: str,
        trading_session: str  # 'pre_open' | 'post_close'
    ) -> AnalystMemorySummary:
        """
        获取 Memory Summary
        
        Args:
            symbol: 股票代码
            trade_date: 交易日期 YYYY-MM-DD
            trading_session: 交易时段
                - 'pre_open': 开盘前，返回 memory_summary_pre_open
                - 'post_close': 收盘后，返回 memory_summary_post_close
        
        Returns:
            AnalystMemorySummary 包含：
            - today_report: 今日报告（如果已生成，对于 Market 是最新快照）
            - memory_summary_pre_open: 开盘前长期记忆摘要
            - memory_summary_post_close: 收盘后长期记忆摘要
        """
        ...


class BaseMemoryController:
    """
    Memory Controller 基类
    
    提供通用的实现框架，各 Analyst 可以继承并扩展。
    使用 LLM 生成记忆摘要。
    """
    
    def __init__(
        self,
        analyst_type: str,
        data_manager: Any,
        llm: BaseChatModel,
        prompt_template_path: Optional[Path] = None
    ):
        """
        初始化 Memory Controller
        
        Args:
            analyst_type: Analyst 类型（'market', 'news', 'sentiment', 'fundamentals'）
            data_manager: DataManager 实例，用于数据持久化
            llm: LLM 实例，用于生成记忆摘要
            prompt_template_path: Prompt 模板路径（可选，使用默认模板）
        """
        self.analyst_type = analyst_type
        self.data_manager = data_manager
        self.llm = llm
        
        # 时间尺度映射
        self.timescale_map = {
            'market': 'intraday',
            'news': 'daily',
            'sentiment': 'daily',
            'fundamentals': 'slow'
        }
        self.timescale = self.timescale_map.get(analyst_type, 'daily')
        
        # 加载 prompt 模板
        if prompt_template_path is None:
            # 使用默认模板路径
            default_template_dir = Path(__file__).parent / "prompts"
            prompt_template_path = default_template_dir / f"{analyst_type}_memory_summary.j2"
        
        self.prompt_template_path = prompt_template_path
    
    def save_today_report(
        self,
        symbol: str,
        trade_date: str,
        report_content: str,
        trade_timestamp: Optional[str] = None
    ) -> bool:
        """
        保存今日报告到数据库
        
        对于 Market Analyst（频繁更新）：
        - 每次调用都会保存一个新的快照
        - trade_timestamp 用于区分不同时间的快照
        """
        return self.data_manager.save_analyst_report(
            report_type=self.analyst_type,
            symbol=symbol,
            trade_date=trade_date,
            report_content=report_content,
            timescale=self.timescale,
            trade_timestamp=trade_timestamp
        )
    
    def _retrieve_historical_reports(
        self,
        symbol: str,
        trade_date: str,
        include_today: bool = True,
        lookback_days: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        从数据库检索历史报告
        
        Args:
            symbol: 股票代码
            trade_date: 交易日期 YYYY-MM-DD
            include_today: 是否包含今日报告
            lookback_days: 回溯天数（None 表示使用默认值）
                - market: 1 天（只取当日快照）
                - news/sentiment: 7 天
                - fundamentals: 30 天
        
        Returns:
            历史报告列表
        """
        # 确定回溯天数
        if lookback_days is None:
            lookback_days_map = {
                'market': 1,  # Market 只取当日快照
                'news': 7,
                'sentiment': 7,
                'fundamentals': 30
            }
            lookback_days = lookback_days_map.get(self.analyst_type, 7)
        
        # 计算日期范围
        end_date = trade_date
        start_date_obj = datetime.strptime(trade_date, '%Y-%m-%d') - timedelta(days=lookback_days)
        start_date = start_date_obj.strftime('%Y-%m-%d')
        
        # 查询报告
        reports = self.data_manager.query_episodic_memory(
            symbol=symbol,
            report_type=self.analyst_type,
            timescale=self.timescale,
            start_date=start_date,
            end_date=end_date,
            active_only=True
        )
        
        # 如果不包含今日，过滤掉今日报告
        if not include_today:
            reports = [r for r in reports if r.get('trade_date') != trade_date]
        
        # 按日期排序（最新的在前）
        reports.sort(key=lambda x: x.get('trade_date', ''), reverse=True)
        
        return reports
    
    def _generate_memory_summary_with_llm(
        self,
        reports: List[Dict[str, Any]],
        summary_type: str,  # 'pre_open' 或 'post_close'
        symbol: str,
        trade_date: str
    ) -> str:
        """
        使用 LLM 生成记忆摘要
        
        Args:
            reports: 历史报告列表
            summary_type: 摘要类型（'pre_open' 或 'post_close'）
            symbol: 股票代码
            trade_date: 交易日期
        
        Returns:
            结构化摘要文本（Markdown 格式）
        """
        if not reports:
            return f"暂无 {self.analyst_type} 历史报告。"
        
        # 格式化报告文本
        reports_text = self._format_reports_for_summary(reports)
        
        # 加载 prompt 模板
        try:
            with open(self.prompt_template_path, "r", encoding="utf-8") as f:
                template = Template(f.read())
        except FileNotFoundError:
            # 如果模板不存在，使用默认模板
            template = self._get_default_template()
        
        # 渲染 prompt
        prompt = template.render(
            analyst_type=self.analyst_type,
            symbol=symbol,
            trade_date=trade_date,
            summary_type=summary_type,
            reports_text=reports_text,
            report_count=len(reports)
        )
        
        # 调用 LLM 生成摘要
        try:
            response = self.llm.invoke(prompt)
            return response.content if hasattr(response, 'content') else str(response)
        except Exception as e:
            # 如果 LLM 调用失败，返回简单摘要
            return f"生成 {summary_type} 摘要时出错: {str(e)}"
    
    def _format_reports_for_summary(
        self,
        reports: List[Dict[str, Any]]
    ) -> str:
        """
        格式化报告列表为文本，用于 LLM 摘要生成
        """
        formatted_text = ""
        
        for i, report in enumerate(reports, 1):
            trade_date = report.get('trade_date', 'N/A')
            trade_timestamp = report.get('trade_timestamp', '')
            content = report.get('report_content', '')
            confidence = report.get('confidence_score', 1.0)
            
            formatted_text += f"\n## 报告 {i}\n"
            formatted_text += f"日期: {trade_date}"
            if trade_timestamp:
                formatted_text += f" 时间: {trade_timestamp}"
            formatted_text += f" 置信度: {confidence}\n\n"
            formatted_text += f"{content}\n\n"
        
        return formatted_text
    
    def _get_default_template(self) -> Template:
        """
        获取默认的 prompt 模板
        """
        template_str = """你是一个专业的金融分析师，负责从历史报告中提取关键信息并生成结构化摘要。

## 任务
从以下 {{ analyst_type }} 分析报告中提取关键信息，生成 {{ summary_type }} 记忆摘要。

## 输入
股票代码: {{ symbol }}
交易日期: {{ trade_date }}
报告数量: {{ report_count }}

历史报告:
{{ reports_text }}

## 输出要求
请生成一个结构化的 Markdown 格式摘要，包含：
1. 关键趋势和模式
2. 重要事件和变化
3. 持续关注的风险因素
4. 对当前决策的参考价值

摘要应该简洁、结构化，便于快速理解历史信息。"""
        
        return Template(template_str)
    
    def _generate_memory_summary_pre_open(
        self,
        symbol: str,
        trade_date: str
    ) -> str:
        """
        生成开盘前长期记忆摘要
        
        从历史报告中提取关键信息，生成结构化摘要
        用于开盘前的决策参考
        
        Returns:
            结构化摘要文本（Markdown 格式）
        """
        # 检索历史报告（排除今日，因为开盘前今日报告可能还未生成）
        reports = self._retrieve_historical_reports(
            symbol=symbol,
            trade_date=trade_date,
            include_today=False
        )
        
        return self._generate_memory_summary_with_llm(
            reports=reports,
            summary_type='pre_open',
            symbol=symbol,
            trade_date=trade_date
        )
    
    def _generate_memory_summary_post_close(
        self,
        symbol: str,
        trade_date: str
    ) -> str:
        """
        生成收盘后长期记忆摘要
        
        包含今日报告和历史摘要，用于收盘后的复盘和下一日准备
        
        对于 Market Analyst：
        - 包含当日所有快照的聚合摘要
        
        Returns:
            结构化摘要文本（Markdown 格式）
        """
        # 检索历史报告（包含今日）
        reports = self._retrieve_historical_reports(
            symbol=symbol,
            trade_date=trade_date,
            include_today=True
        )
        
        return self._generate_memory_summary_with_llm(
            reports=reports,
            summary_type='post_close',
            symbol=symbol,
            trade_date=trade_date
        )
    
    def get_memory_summary(
        self,
        symbol: str,
        trade_date: str,
        trading_session: str
    ) -> AnalystMemorySummary:
        """
        获取 Memory Summary
        
        根据 trading_session 返回相应的摘要
        """
        # 获取今日报告（如果已生成）
        # 对于 Market，返回最新快照；对于其他，返回今日唯一报告
        today_report = self._get_today_report(symbol, trade_date)
        
        # 根据交易时段生成相应的记忆摘要
        if trading_session == 'pre_open':
            memory_summary_pre_open = self._generate_memory_summary_pre_open(
                symbol, trade_date
            )
            memory_summary_post_close = ""  # 开盘前不生成收盘后摘要
        else:  # post_close
            memory_summary_pre_open = self._generate_memory_summary_pre_open(
                symbol, trade_date
            )
            memory_summary_post_close = self._generate_memory_summary_post_close(
                symbol, trade_date
            )
        
        return {
            'today_report': today_report,
            'memory_summary_pre_open': memory_summary_pre_open,
            'memory_summary_post_close': memory_summary_post_close
        }
    
    def _get_today_report(
        self,
        symbol: str,
        trade_date: str
    ) -> str:
        """
        获取今日报告（如果已生成）
        
        对于 Market Analyst（频繁更新）：
        - 返回最新的快照报告
        
        对于其他 Analyst：
        - 返回今日的唯一报告
        """
        # 查询今日报告
        reports = self._retrieve_historical_reports(
            symbol=symbol,
            trade_date=trade_date,
            include_today=True,
            lookback_days=1  # 只查询今日
        )
        
        if not reports:
            return ""
        
        # 对于 Market，返回最新的快照（按时间戳排序）
        if self.analyst_type == 'market':
            # 按 trade_timestamp 排序，取最新的
            reports_with_timestamp = [
                r for r in reports 
                if r.get('trade_timestamp')
            ]
            if reports_with_timestamp:
                reports_with_timestamp.sort(
                    key=lambda x: x.get('trade_timestamp', ''),
                    reverse=True
                )
                return reports_with_timestamp[0].get('report_content', '')
        
        # 对于其他 Analyst，返回最新的报告
        return reports[0].get('report_content', '')

