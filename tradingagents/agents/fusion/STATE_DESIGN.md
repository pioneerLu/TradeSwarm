# State 设计文档

## 设计原则

系统采用**两层 State 结构**：

1. **Analyst 私有 State**：每个 Analyst 节点内部使用，不共享
2. **Fusion 共享 State**：由 Fusion 构建，供 Researcher 和 Risk Manager 使用

## 架构图

```
┌─────────────────────────────────────────────────────────┐
│                    Analyst 阶段                           │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  Market Analyst          News Analyst                    │
│  ┌─────────────┐        ┌─────────────┐                 │
│  │ Private     │        │ Private     │                 │
│  │ State       │        │ State       │                 │
│  └──────┬──────┘        └──────┬──────┘                 │
│         │                       │                        │
│         │ 生成报告               │ 生成报告                │
│         ↓                       ↓                        │
│  ┌──────────────┐        ┌──────────────┐               │
│  │ Memory       │        │ Memory       │               │
│  │ Controller   │        │ Controller   │               │
│  └──────────────┘        └──────────────┘               │
│                                                           │
│  Sentiment Analyst        Fundamentals Analyst           │
│  ┌─────────────┐        ┌─────────────┐               │
│  │ Private     │        │ Private     │                 │
│  │ State       │        │ State       │                 │
│  └──────┬──────┘        └──────┬──────┘                 │
│         │                       │                        │
│         │ 生成报告               │ 生成报告                │
│         ↓                       ↓                        │
│  ┌──────────────┐        ┌──────────────┐               │
│  │ Memory       │        │ Memory       │               │
│  │ Controller   │        │ Controller   │               │
│  └──────────────┘        └──────────────┘               │
│                                                           │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                    Fusion 阶段                            │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  Fusion Node                                             │
│  ┌──────────────────────────────────────┐                │
│  │  从四个 Memory Controller 读取：      │                │
│  │  - today_report                      │                │
│  │  - memory_summary_pre_open           │                │
│  │  - memory_summary_post_close         │                │
│  └──────────────┬───────────────────────┘                │
│                 │                                         │
│                 │ 结构化聚合                               │
│                 ↓                                         │
│  ┌──────────────────────────────────────┐                │
│  │      Fusion State                    │                │
│  │  (Researcher & Risk Manager 共享)    │                │
│  └──────────────────────────────────────┘                │
│                                                           │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│              Researcher & Risk Manager 阶段              │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  Researcher              Risk Manager                     │
│  ┌─────────────┐        ┌─────────────┐                 │
│  │ 读取并更新   │        │ 读取并更新   │                 │
│  │ Fusion State│        │ Fusion State│                 │
│  └─────────────┘        └─────────────┘                 │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

## State 结构

### 1. Analyst 私有 State

每个 Analyst 的私有 State 只用于节点内部执行，包含：

- `company_of_interest`: 股票代码
- `trade_date`: 交易日期
- `trade_timestamp`: 精确时间戳（仅 Market Analyst 需要，分钟级）
- `*_report`: 生成的报告（临时，生成后写入 Memory Controller）
- `messages`: LLM 交互历史（临时）

**特点：**
- 不共享，不进入全局 State
- 报告生成后写入 Memory Controller，State 可丢弃
- 每个 Analyst 独立，互不通信

### 2. Memory Controller

每个 Analyst 对应一个 Memory Controller，负责：

1. **维护历史报告**：保存该 Analyst 的所有历史报告
2. **生成记忆摘要**：按时间段生成摘要
   - `memory_summary_pre_open`: 开盘前长期记忆摘要
   - `memory_summary_post_close`: 收盘后长期记忆摘要
3. **对外接口**：提供统一的 `get_memory_summary()` 接口

**Memory Summary 结构：**
```python
{
    'today_report': str,                    # 今日报告（如果已生成）
    'memory_summary_pre_open': str,        # 开盘前摘要
    'memory_summary_post_close': str        # 收盘后摘要
}
```

### 3. Fusion State

由 Fusion 节点构建，供 Researcher 和 Risk Manager 共享使用。

**结构：**
```python
{
    # 基础信息
    'company_of_interest': str,
    'trade_date': str,
    'trade_timestamp': Optional[str],
    
    # 四个 Analyst 的 Memory Summary
    'market_analyst_summary': AnalystMemorySummary,
    'news_analyst_summary': AnalystMemorySummary,
    'sentiment_analyst_summary': AnalystMemorySummary,
    'fundamentals_analyst_summary': AnalystMemorySummary,
    
    # 聚合结论（结构化，非原始文本）
    'aggregated_insights': {
        'consensus_points': List[str],
        'conflict_points': List[str],
        'market_sentiment': str,
        'confidence_scores': Dict[str, float],
        'key_constraints': List[str],
        'risk_factors': List[str]
    },
    
    # 市场元信息
    'market_metadata': {
        'trading_session': str,
        'volatility_level': float,
        'liquidity_status': str
    },
    
    # Manager 状态（由 Manager 维护）
    'position_state': Optional[Dict],
    'risk_exposure': Optional[Dict],
    'execution_results': Optional[Dict]
}
```

**特点：**
- 字段清晰、无时间序列
- 仅服务于当期决策
- 不包含原始报告全文，只包含结构化摘要

## 工作流程

### Analyst 阶段

1. Analyst 节点接收输入（股票代码、日期等）
2. Analyst 使用私有 State 执行分析
3. 生成报告后，调用 Memory Controller 的 `save_today_report()` 保存
4. Analyst 私有 State 可丢弃

### Fusion 阶段

1. Fusion 节点从四个 Memory Controller 读取 Memory Summary
   ```python
   market_summary = market_memory_controller.get_memory_summary(
       symbol, trade_date, trading_session
   )
   news_summary = news_memory_controller.get_memory_summary(
       symbol, trade_date, trading_session
   )
   # ... 其他两个
   ```

2. 聚合四个 Summary，生成结构化结论
   - 识别共识点
   - 识别冲突点
   - 评估置信度
   - 提取约束条件和风险因素

3. 构建 Fusion State
   - 包含四个 Analyst 的 Memory Summary
   - 包含聚合结论
   - 包含市场元信息
   - 包含 Manager 状态（从上一周期继承或初始化）

### Researcher & Risk Manager 阶段

1. 读取 Fusion State
2. 基于 Fusion State 进行推理和决策
3. 更新 Fusion State（仅限各自权限范围）
   - Researcher: 更新非交易相关字段
   - Risk Manager: 更新交易和风险相关字段

## 时间尺度对应

| Analyst | 时间尺度 | Memory Summary 更新频率 |
|---------|---------|----------------------|
| Market | intraday (分钟级) | 每次生成报告后更新 today_report |
| News | daily (天级) | 每日收盘后更新 memory_summary_post_close |
| Sentiment | daily (天级) | 每日收盘后更新 memory_summary_post_close |
| Fundamentals | slow (周级) | 每周更新 memory_summary_post_close |

## 实现要点

1. **Analyst 隔离**：Analyst 不读取全局 State，不跨 Analyst 通信
2. **Memory Controller 职责**：维护历史、生成摘要、提供接口
3. **Fusion 聚合**：结构化聚合，不简单拼接
4. **State 清晰性**：Fusion State 字段清晰，无时间序列，仅服务于当期决策

