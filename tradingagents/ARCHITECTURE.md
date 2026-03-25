# 交易系统架构说明

## 目录结构

```
tradingagents/
├── agents/
│   ├── pre_open/          # 开盘前分析阶段
│   │   ├── trader/        # 交易员节点（可访问仓位信息）
│   │   ├── managers/
│   │   │   ├── research_manager/  # 研究侧辩论收口（对齐上游 Research Manager）
│   │   │   └── risk_manager/      # 风险辩论终审（对齐上游 Portfolio Manager）
│   │   └── ...
│   ├── market_open/       # 信号解析（如 signal_resolver → QuantConnect）
│   └── post_close/        # 收盘后：历史维护、反思等
│       ├── history_maintainer.py
│       └── reflector.py
│
├── core/                   # 核心模块
│   ├── selection/          # 选股服务
│   │   └── stock_selector.py
│   └── data_adapter.py     # 数据适配器
│
└── graph/
    └── trading_graph.py    # 主交易图
```

## 流程说明

### 1. Pre-Open（开盘前分析）

**节点顺序**：
```
Summary Nodes → Research Subgraph → Trader → Risk Subgraph
```

**关键特性**：
- `Trader` 节点可以访问 `current_position` 和 `portfolio_state`
- `Risk Manager` 节点可以访问 `current_position` 和 `portfolio_state`
- 生成可执行交易决策（action/target_pct/entry_type/entry_price），但不执行交易

### 与上游 [TradingAgents](https://github.com/TauricResearch/TradingAgents) 的对应关系

| 上游（TauricResearch） | 本仓库（TradeSwarm） | 说明 |
|------------------------|----------------------|------|
| Research Manager | `research_manager` | 牛熊辩论后收口研究结论；本仓库要求 **结构化 JSON**（`decision` / `rationale` / `action_plan` 等），而非上游仓库中的纯自然语言段落。 |
| Portfolio Manager | `risk_manager` | 风险辩论后给出终审与仓位/风控约束；本仓库用 **`final_decision`（BUY/SELL/HOLD）+ `position_size` 等** 与 `signal_resolver` 合并，便于 QuantConnect 与单测。 |
| Trader | `trader` | 本仓库由 Trader 直接产出可执行字段，再经 Risk 层约束。 |

保留 **JSON + [`signal_resolver`](agents/market_open/signal_resolver.py)** 的原因：下游回测与导出脚本需要稳定字段与可校验输出；上游的 `SignalProcessor` 解析自然语言的路径与本仓库目标不一致，故不照搬。

### 2. Market Open（执行侧）

实盘/回测下单由 **QuantConnect**（或外部执行器）消费导出信号；Python 侧通过 `signal_resolver` 从 `trader_investment_plan` 与 `risk_summary` 合并出结构化信号。

**职责（概念上）**：
- 读取 Pre-Open 的 `trader_investment_plan`、`risk_summary`
- 按 `entry_type` / `entry_price` 等字段执行或回测下单

### 3. Post-Close（收盘后）

主要模块：`history_maintainer`、`reflector` 等，用于维护分析脉络与反思记录；组合级收盘核算可能在外部回测/实盘系统中完成。

## AgentState 扩展

在 `AgentState` 中添加了以下字段：

```python
current_position: Optional[Dict[str, Any]]  # 当前持仓信息
portfolio_state: Optional[Dict[str, Any]]   # 组合状态
```

## 组合与选股（core）

### StockSelectorService

位置：`tradingagents/core/selection/stock_selector.py`

功能：
- 封装 `trading_sys` 的选股功能
- 每月第一个交易日选股
- 判断再平衡日

## 使用方式

Pre-Open 决策图入口：[`graph/trading_graph.py`](graph/trading_graph.py) 的 `create_trading_graph`；信号导出见仓库根目录脚本 `scripts/runtime/run_signal_export.py` 与 `quantconnect/`。

## 关键设计

1. **时间处理**：T 日收盘后计算信号，T+1 日开盘价执行交易
2. **风险控制**：如果 Risk Manager 决策为 HOLD，不执行交易
3. **仓位管理**：均分仓位，每个股票分配 `1 / len(target_symbols)` 的仓位
4. **仓位信息共享**：`trader` 和 `risk_manager` 节点都可以访问仓位信息，做出更准确的决策

