# Memory Controller 实现指南

## 核心设计

Memory Controller 是连接 Analyst 报告与 Fusion State 的关键中间层。其职责是维护报告历史并生成结构化的记忆摘要。

## 架构概览

```
Analyst Node
    ↓ save_today_report()
Memory Controller
    ↓ episodic memory (报告数据库)
    ↓ _generate_memory_summary_*()
    ↓ get_memory_summary() → AnalystMemorySummary
Fusion Node
    ↓ 填充 FusionState
```

## 关键字段映射

### AnalystMemorySummary 结构

每个 Memory Controller 的 `get_memory_summary()` 返回此结构：

```python
{
    'today_report': str,                    # 今日报告快照
    'memory_summary_pre_open': str,        # 开盘前的历史摘要
    'memory_summary_post_close': str        # 收盘后的历史摘要
}
```

**字段语义说明：**

| 字段 | 含义 | 何时填充 | 特殊处理 |
|-----|------|---------|--------|
| `today_report` | 当日生成的最新报告 | 仅 post_close 时包含 | Market 返回最新快照；其他返回唯一报告 |
| `memory_summary_pre_open` | 开盘前的长期记忆摘要 | 两个时段都生成 | 来自历史报告的 LLM 聚合 |
| `memory_summary_post_close` | 收盘后的长期记忆摘要 | 仅 post_close 时生成 | 包含当日报告，供下一日参考 |

### 时间段逻辑（trading_session）

#### 开盘前（pre_open）
```python
trading_session = 'pre_open'

return {
    'today_report': '',                        # 空，开盘还未开始
    'memory_summary_pre_open': '...',         # 生成：历史报告 LLM 聚合
    'memory_summary_post_close': ''           # 空，不需要
}
```

**场景**：早晨 9:30 开盘前，Fusion 从历史数据中学习趋势

#### 收盘后（post_close）
```python
trading_session = 'post_close'

return {
    'today_report': '...',                     # 填充：当日最新报告
    'memory_summary_pre_open': '...',         # 生成：历史摘要（用于对比）
    'memory_summary_post_close': '...'        # 生成：包含当日的新摘要
}
```

**场景**：收盘后 16:00，当日报告已生成，进行复盘和下一日准备

## 各 Analyst 的实现差异

### Market Analyst（分钟级 - intraday）

**特点**：频繁更新（每分钟可能多次调用 `save_today_report`）

**实现要点**：
```python
def save_today_report(symbol, trade_date, report_content, trade_timestamp):
    # 每次调用都保存一个快照
    # trade_timestamp: "YYYY-MM-DD HH:MM:SS"（如 "2024-01-15 10:30:45"）
    return self.data_manager.save_analyst_report(
        report_type='market',
        symbol=symbol,
        trade_date=trade_date,
        report_content=report_content,
        trade_timestamp=trade_timestamp,
        timescale='intraday'
    )

def _get_today_report(symbol, trade_date):
    # 查询当日所有快照，按 trade_timestamp 排序
    snapshots = query_by_timestamp(symbol, trade_date)
    if snapshots:
        # 返回最新的快照（timestamp 最大）
        return snapshots[-1]['report_content']
    return ""
```

**lookback_days**: 仅 1 天（当日快照）

### News / Sentiment Analyst（天级 - daily）

**特点**：每日固定更新（开盘前或收盘后一次）

**实现要点**：
```python
def save_today_report(symbol, trade_date, report_content):
    # 不需要 trade_timestamp，日期维度足够
    return self.data_manager.save_analyst_report(
        report_type='news',  # 或 'sentiment'
        symbol=symbol,
        trade_date=trade_date,
        report_content=report_content,
        timescale='daily'
    )

def _get_today_report(symbol, trade_date):
    # 查询当日报告，通常仅有一份
    reports = query_by_date(symbol, trade_date)
    if reports:
        return reports[0]['report_content']
    return ""
```

**lookback_days**: 7 天（一周滚动窗口）

### Fundamentals Analyst（周级 - slow）

**特点**：按周更新（每周更新一次基本面数据）

**实现要点**：
```python
def save_today_report(symbol, trade_date, report_content):
    # trade_date 是本周某个交易日，但报告代表本周基本面
    return self.data_manager.save_analyst_report(
        report_type='fundamentals',
        symbol=symbol,
        trade_date=trade_date,
        report_content=report_content,
        timescale='slow'
    )

def _get_today_report(symbol, trade_date):
    # 查询当周报告（如果有的话）
    # 通常本周内只有最多一份基本面报告
    reports = query_by_week(symbol, trade_date)
    if reports:
        return reports[-1]['report_content']  # 最新的
    return ""
```

**lookback_days**: 30 天（近一个月的趋势）

## LLM 摘要生成流程

### 关键问题

1. **去重与去噪**：历史报告中可能有大量重复或过时信息
   - 建议：在格式化报告前，使用相似度算法（余弦相似度）过滤相近的报告
   - 仅保留过去 N 天内的**代表性报告**（3-5 份足够）

2. **语境注入**：LLM 生成摘要时需要知道上下文
   - pre_open 摘要：聚焦**历史趋势和持续风险**
   - post_close 摘要：聚焦**当日关键事件和变化**，为下一日提供指导

3. **结构化输出**：确保摘要内容一致且可被 Fusion 节点可靠解析
   - 建议格式：Markdown with 明确的分部分标题（## 关键趋势、## 风险因素等）
   - 避免过长：控制在 500-1000 字符内

### Prompt 模板框架

```jinja2
你是一个{{ analyst_type }}分析专家，需要从历史报告中提取关键信息。

## 任务
根据以下{{ report_count }}份历史报告，生成一份{{ summary_type }}摘要。

## 输入信息
- 股票代码：{{ symbol }}
- 交易日期：{{ trade_date }}
- 报告跨度：{{ start_date }}至{{ end_date }}

## 历史报告
{{ reports_text }}

## 输出要求
生成一份结构化 Markdown 摘要，包含：
1. **关键趋势**：过去一周/月的主要走势
2. **重要事件**：影响股价的关键事件
3. **风险因素**：需要持续关注的风险
4. **信号强度**：本摘要的确信度（高/中/低）

摘要应精确、可操作，方便决策参考。
```

## 数据一致性保证

### 版本控制

每份报告应包含元数据：
```python
{
    'report_id': uuid,                  # 唯一标识
    'analyst_type': 'market',           # Analyst 类型
    'symbol': '000001',
    'trade_date': '2024-01-15',
    'trade_timestamp': '2024-01-15 10:30:45',  # Market 特有
    'report_content': '...',            # 报告正文
    'confidence_score': 0.85,           # 报告置信度（可选）
    'created_at': '2024-01-15T10:30:45Z',    # 保存时间戳
    'timescale': 'intraday'             # 时间尺度
}
```

### 查询优化

建议在数据库层面建立索引：
```
Index: (analyst_type, symbol, trade_date, timescale)
Index: (symbol, trade_date, trade_timestamp)  # Market 专用
```

## Fusion Node 调用示例

```python
# Fusion 节点的实现框架
class FusionNode:
    def __init__(self, memory_controllers: Dict[str, IMemoryController]):
        self.market_mc = memory_controllers['market']
        self.news_mc = memory_controllers['news']
        self.sentiment_mc = memory_controllers['sentiment']
        self.fundamentals_mc = memory_controllers['fundamentals']
    
    def build_fusion_state(self, symbol: str, trade_date: str, trading_session: str) -> FusionState:
        # 从四个 Memory Controller 拉取摘要
        market_summary = self.market_mc.get_memory_summary(symbol, trade_date, trading_session)
        news_summary = self.news_mc.get_memory_summary(symbol, trade_date, trading_session)
        sentiment_summary = self.sentiment_mc.get_memory_summary(symbol, trade_date, trading_session)
        fundamentals_summary = self.fundamentals_mc.get_memory_summary(symbol, trade_date, trading_session)
        
        # 从其他数据源填充实盘数据
        account_data = self.account_system.get_account_info()
        market_data = self.market_data_provider.get_latest_price(symbol)
        
        # 构建 FusionState
        return FusionState(
            company_of_interest=symbol,
            trade_date=trade_date,
            trade_timestamp=datetime.now().isoformat() if trading_session == 'post_close' else None,
            
            # Analyst Memory
            market_analyst_summary=market_summary,
            news_analyst_summary=news_summary,
            sentiment_analyst_summary=sentiment_summary,
            fundamentals_analyst_summary=fundamentals_summary,
            
            # 实盘数据
            account_cash=account_data['available_cash'],
            account_total_value=account_data['total_value'],
            current_price=market_data['close'],
            previous_close=market_data['previous_close'],
            portfolio_positions=account_data['positions'],
            
            # 初始化决策字段
            research_summary=None,
            risk_summary=None,
            investment_plan=None,
            trader_investment_plan=None,
            final_trade_decision=None
        )
```

## 检查清单

在实现 Memory Controller 时，确保：

- [ ] `get_memory_summary()` 根据 `trading_session` 正确填充字段
- [ ] Market Analyst 的 `trade_timestamp` 处理逻辑清晰
- [ ] LLM 摘要生成使用结构化 Prompt，输出格式一致
- [ ] 数据库查询使用适当的索引，性能满足要求
- [ ] 历史报告的去重逻辑避免信息冗余
- [ ] 错误处理：若摘要生成失败，返回降级方案（如简单拼接）
- [ ] 单元测试覆盖各 Analyst 类型和时间段组合

