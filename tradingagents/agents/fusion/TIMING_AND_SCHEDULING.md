# 时间触发与调度设计

## 时间尺度与更新频率

| Analyst | 时间尺度 | 更新频率 | 触发时机 | 说明 |
|---------|---------|---------|---------|------|
| Market | intraday (分钟级) | 频繁更新（1-5分钟） | 盘中持续触发 | 每次生成快照报告 |
| News | daily (天级) | 每日一次 | **开盘前（9:30前）** | 用于指导当日策略 |
| Sentiment | daily (天级) | 每日一次 | **开盘前（9:30前）** | 用于指导当日策略 |
| Fundamentals | slow (周级) | 每周一次 | 周末或周一开盘前 | 低频更新 |

## Market Analyst 频繁更新机制

### 设计思路

Market Analyst 需要频繁更新（分钟级），与其他 Analyst 的每日更新不同。

**关键设计：**
1. **快照机制**：每次运行生成一个快照报告，保存时带时间戳
2. **最新快照优先**：`today_report` 始终返回最新的快照
3. **聚合摘要**：收盘后生成当日所有快照的聚合摘要

### 实现细节

#### 1. 保存快照

```python
# Market Analyst 每次运行后
market_memory_controller.save_today_report(
    symbol="000001",
    trade_date="2025-01-15",
    report_content=market_report,
    trade_timestamp="2025-01-15 14:30:00"  # 分钟级时间戳
)
```

#### 2. 获取最新快照

```python
# Fusion 读取时
market_summary = market_memory_controller.get_memory_summary(
    symbol="000001",
    trade_date="2025-01-15",
    trading_session="open"  # 盘中
)

# market_summary['today_report'] 是最新的快照
```

#### 3. 收盘后聚合

收盘后，Memory Controller 会：
1. 检索当日所有快照
2. 使用 LLM 生成聚合摘要（`memory_summary_post_close`）
3. 摘要包含当日市场趋势、关键转折点等

### 触发机制

**盘中（9:30 - 15:00）：**
- 定时触发：每 1-5 分钟运行一次 Market Analyst
- 事件触发：价格/成交量异常时立即触发
- 每次生成快照，更新 `today_report`

**收盘后（15:00 后）：**
- 生成当日所有快照的聚合摘要
- 更新 `memory_summary_post_close`

## News/Sentiment 开盘前更新

### 设计思路

News 和 Sentiment Analyst 在**开盘前（9:30前）**更新，确保：
1. 当日策略制定时能获取最新信息
2. 开盘前有足够时间生成报告
3. 报告可用于指导当日交易决策

### 触发时机

**建议时间：**
- **8:00 - 9:00**：运行 News Analyst
- **8:30 - 9:15**：运行 Sentiment Analyst
- **9:15 - 9:30**：运行 Fusion，聚合所有 Analyst 的 Memory Summary

### 实现建议

```python
# 定时任务示例（使用 APScheduler 或类似库）
from apscheduler.schedulers.blocking import BlockingScheduler

scheduler = BlockingScheduler()

# News Analyst：每日 8:00 运行
@scheduler.scheduled_job('cron', hour=8, minute=0)
def run_news_analyst():
    # 运行 News Analyst
    # 保存报告到 Memory Controller
    pass

# Sentiment Analyst：每日 8:30 运行
@scheduler.scheduled_job('cron', hour=8, minute=30)
def run_sentiment_analyst():
    # 运行 Sentiment Analyst
    # 保存报告到 Memory Controller
    pass

# Fusion：每日 9:15 运行（开盘前）
@scheduler.scheduled_job('cron', hour=9, minute=15)
def run_fusion():
    # 从四个 Memory Controller 读取 Memory Summary
    # 构建 Fusion State
    # 供 Researcher 和 Risk Manager 使用
    pass
```

## Fusion 定时触发

### 设计思路

Fusion 可以定时触发，从四个 Analyst 的 Memory Controller 中聚合信息。

**触发频率：**
- **开盘前**：9:15（聚合开盘前的信息）
- **盘中**：每 15-30 分钟（更新 Market 最新快照）
- **收盘后**：15:30（生成收盘后摘要）

### 实现建议

```python
# Fusion 节点实现
def create_fusion_node(
    llm: BaseChatModel,
    market_memory_controller: IMemoryController,
    news_memory_controller: IMemoryController,
    sentiment_memory_controller: IMemoryController,
    fundamentals_memory_controller: IMemoryController
):
    def fusion_node(state: Optional[FusionState]) -> FusionState:
        symbol = state.get("company_of_interest") if state else "000001"
        trade_date = state.get("trade_date") if state else datetime.now().strftime("%Y-%m-%d")
        
        # 确定交易时段
        current_time = datetime.now().time()
        if current_time < time(9, 30):
            trading_session = "pre_open"
        elif current_time >= time(15, 0):
            trading_session = "post_close"
        else:
            trading_session = "open"
        
        # 从四个 Memory Controller 读取 Memory Summary
        market_summary = market_memory_controller.get_memory_summary(
            symbol, trade_date, trading_session
        )
        news_summary = news_memory_controller.get_memory_summary(
            symbol, trade_date, trading_session
        )
        sentiment_summary = sentiment_memory_controller.get_memory_summary(
            symbol, trade_date, trading_session
        )
        fundamentals_summary = fundamentals_memory_controller.get_memory_summary(
            symbol, trade_date, trading_session
        )
        
        # 聚合并构建 Fusion State
        # ... 聚合逻辑 ...
        
        return fusion_state
    
    return fusion_node
```

## 时间线示例

### 典型交易日时间线

```
08:00 - News Analyst 运行
        ↓ 生成报告，保存到 Memory Controller

08:30 - Sentiment Analyst 运行
        ↓ 生成报告，保存到 Memory Controller

09:15 - Fusion 运行（开盘前）
        ↓ 读取四个 Memory Controller 的 Memory Summary
        ↓ 构建 Fusion State（trading_session='pre_open'）
        ↓ 供 Researcher 和 Risk Manager 使用

09:30 - 开盘
        ↓ Market Analyst 开始频繁运行（每 1-5 分钟）

10:00 - Fusion 运行（盘中）
        ↓ 更新 Market 最新快照
        ↓ 更新 Fusion State（trading_session='open'）

14:00 - Fusion 运行（盘中）
        ↓ 更新 Market 最新快照
        ↓ 更新 Fusion State

15:00 - 收盘

15:30 - Fusion 运行（收盘后）
        ↓ 生成收盘后摘要
        ↓ 更新 Fusion State（trading_session='post_close'）
        ↓ 为下一日准备
```

## 注意事项

1. **Market 频繁更新**：
   - 每次更新都会保存新快照（带时间戳）
   - `today_report` 始终是最新的
   - 收盘后生成聚合摘要，避免信息过载

2. **开盘前更新**：
   - News 和 Sentiment 必须在 9:30 前完成
   - 确保 Fusion 能在开盘前聚合信息
   - 为策略制定留出时间

3. **Fusion 触发**：
   - 可以定时触发
   - 也可以事件驱动（如 Market 快照更新后）
   - 根据 `trading_session` 生成相应的 Memory Summary

4. **时间同步**：
   - 确保系统时间准确
   - 考虑时区问题
   - 交易日判断（排除节假日）

