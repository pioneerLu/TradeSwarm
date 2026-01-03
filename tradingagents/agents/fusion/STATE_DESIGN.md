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
- `trade_date`: 交易日期（YYYY-MM-DD）
- `trade_timestamp`: 精确时间戳（可选，仅 Market Analyst 需要，格式 YYYY-MM-DD HH:MM:SS）
- `messages`: LLM 交互消息列表（继承自 MessagesState 或自定义）
- `*_report`: 生成的报告（临时，生成后写入 Memory Controller）

**特点：**
- 不共享，不进入全局 State
- 报告生成后调用 Memory Controller 的 `save_today_report()` 保存
- State 生成后可丢弃
- 每个 Analyst 独立执行，互不通信

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
    'company_of_interest': str,                           # 目标股票代码
    'trade_date': str,                                   # 交易日期 YYYY-MM-DD
    'trade_timestamp': Optional[str],                    # 精确时间戳
    
    # 四个 Analyst 的 Memory Summary（由 Memory Controller 提供）
    'market_analyst_summary': AnalystMemorySummary,      # {today_report, memory_summary_pre_open, memory_summary_post_close}
    'news_analyst_summary': AnalystMemorySummary,
    'sentiment_analyst_summary': AnalystMemorySummary,
    'fundamentals_analyst_summary': AnalystMemorySummary,
    
    # 最终决策输出（仅包含结论，无辩论过程）
    'research_summary': Optional[Dict[str, Any]],        # Research Manager 的最终投资决策
    'risk_summary': Optional[Dict[str, Any]],            # Risk Manager 的风险评估结论
    'investment_plan': Optional[str],                    # 投资计划文本摘要
    'trader_investment_plan': Optional[str],             # Trader 生成的最终执行计划
    'final_trade_decision': Optional[str],               # 最终交易决策
    
    # 账户与持仓数据（实盘化）
    'account_cash': float,                               # 账户可用现金（元）
    'account_total_value': float,                        # 账户总权益（现金 + 持仓市值）
    'current_price': float,                              # 当前股票价格
    'previous_close': Optional[float],                   # 前一日收盘价
    'portfolio_positions': Dict[str, Dict[str, Any]],    # 持仓结构（支持多持仓）
    'max_drawdown': Optional[float],                     # 账户最大回撤百分比
    
    # 执行记录
    'execution_record': Optional[Dict[str, Any]]         # 下单执行日志与结果
}
```

**AnalystMemorySummary 结构：**
```python
{
    'today_report': str,                    # 今日报告（如果已生成）
    'memory_summary_pre_open': str,        # 开盘前长期记忆摘要
    'memory_summary_post_close': str        # 收盘后长期记忆摘要
}
```

**特点：**
- 字段清晰，分层次组织
- 仅保留最终决策与定量交易数据
- 辩论过程完全隔离在子图（Subgraph）内，不污染全局 State
- 支持精确的风控计算与实盘下单

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

2. 从四个 Memory Controller 拉取 AnalystMemorySummary，填充到 FusionState：
   ```python
   market_summary = market_memory_controller.get_memory_summary(
       symbol, trade_date, trading_session
   )
   news_summary = news_memory_controller.get_memory_summary(
       symbol, trade_date, trading_session
   )
   # ... 其他两个
   ```

3. 填充账户与市场数据
   - 从持仓系统读取 account_cash, portfolio_positions 等
   - 从行情数据源读取 current_price, previous_close 等

4. 构建完整的 Fusion State
   - 包含四个 Analyst 的 Memory Summary
   - 包含账户与持仓数据
   - 初始化决策相关字段（research_summary, risk_summary 等为 None）

### Researcher & Risk Manager 阶段（子图隔离）

1. **Research 子图**：
   - 接收 FusionState 作为输入
   - 在隔离的 InvestDebateState 中进行多轮牛熊辩论
   - 生成 `investment_plan` 和 `research_summary`
   - 将结果写回 FusionState

2. **Risk Manager 子图**：
   - 接收更新后的 FusionState（包含 research_summary）
   - 在隔离的 RiskDebateState 中进行多角色风险评估
   - 基于 account_cash 和 portfolio_positions 进行精确风控计算
   - 生成 `final_trade_decision` 和 `risk_summary`
   - 将结果写回 FusionState

3. **Trader 节点**：
   - 消费 FusionState 中的结构化决策
   - 执行 `final_trade_decision`
   - 更新 `execution_record`

## 子图隔离设计

为了保持全局 FusionState 的清晰性和简洁性，Researcher 和 Risk Manager 的辩论过程采用**完全隔离的子图 State**。辩论过程中的消息链、中间状态都在子图内部维护，最终仅将决策结果写回 FusionState。

### InvestDebateState（Researcher 子图）

```python
class InvestDebateState(MessagesState):
    """Research 子图辩论状态（完全隔离）"""
    
    # ===== Input (从 FusionState 接收) =====
    company_of_interest: str
    market_analyst_summary: AnalystMemorySummary
    news_analyst_summary: AnalystMemorySummary
    sentiment_analyst_summary: AnalystMemorySummary
    fundamentals_analyst_summary: AnalystMemorySummary
    
    # ===== Internal Process (子图内部维护) =====
    messages: List[BaseMessage]      # 由 MessagesState 自动管理
    latest_speaker: Optional[str]    # bull / bear / judge
    count: int                        # 当前辩论轮次
    
    # ===== Output (写回 FusionState) =====
    investment_plan: Optional[str]
    research_summary: Optional[Dict[str, Any]]
```

### RiskDebateState（Risk Manager 子图）

```python
class RiskDebateState(MessagesState):
    """Risk Manager 子图辩论状态（完全隔离）"""
    
    # ===== Input (从 FusionState 接收) =====
    company_of_interest: str
    investment_plan: str              # 来自 Research
    research_summary: Dict[str, Any]
    account_cash: float               # 实盘化数据
    current_price: float
    portfolio_positions: Dict[str, Dict[str, Any]]
    
    # ===== Internal Process (子图内部维护) =====
    messages: List[BaseMessage]           # 由 MessagesState 自动管理
    latest_speaker: Optional[str]         # risky / safe / neutral / judge
    count: int                            # 当前辩论轮次
    
    # ===== Output (写回 FusionState) =====
    final_trade_decision: Optional[str]
    risk_summary: Optional[Dict[str, Any]]
```

**子图隔离的核心优势：**

1. **消息链隔离**：子图的所有消息交互（bull vs bear 的多轮对话）都在子图 State 的 messages 中，不污染全局 FusionState
2. **独立决策**：每个子图独立进行推理和决策，生成最终结果
3. **数据流清晰**：子图通过 Input 字段接收外部数据，通过 Output 字段写回结果
4. **易于调试和审计**：子图的完整对话和决策过程可以独立保存和回放

---

## 时间尺度对应

| Analyst | 时间尺度 | Memory Summary 更新频率 |
|---------|---------|----------------------|
| Market | intraday (分钟级) | 每次生成报告后更新 today_report |
| News | daily (天级) | 每日收盘后更新 memory_summary_post_close |
| Sentiment | daily (天级) | 每日收盘后更新 memory_summary_post_close |
| Fundamentals | slow (周级) | 每周更新 memory_summary_post_close |

## 实现要点

1. **Analyst 隔离**：
   - 各 Analyst 独立执行，不读取全局 State
   - Analyst 生成报告后调用 Memory Controller 保存，不直接写入 FusionState

2. **Memory Controller 职责**：
   - 维护 Analyst 的历史报告
   - 按时间段（pre_open/post_close）生成记忆摘要
   - 对外提供统一的 `get_memory_summary()` 接口

3. **Fusion 聚合**：
   - 从四个 Memory Controller 拉取 Summary
   - 填充账户和市场数据
   - 初始化全局 State

4. **子图隔离**：
   - Research 和 Risk Manager 采用独立的子图 State
   - 辩论过程（消息链）完全隔离，不污染全局 FusionState
   - 仅将结构化的最终结果写回 FusionState

5. **数据流向**：
   ```
   Analyst → Memory Controller → Fusion Node
                                    ↓
                              FusionState
                                    ↓
                    ┌───────────────┴───────────────┐
                    ↓                               ↓
            Research 子图 State          Risk Manager 子图 State
            (InvestDebateState)         (RiskDebateState)
                    ↓                               ↓
                    └───────────────┬───────────────┘
                                    ↓
                          更新后的 FusionState
                                    ↓
                              Trader Node
   ```

