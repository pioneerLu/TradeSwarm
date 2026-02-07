# Graph 模块

本模块提供完整的交易决策图构建功能，参考 [TradingAgents](https://github.com/TauricResearch/TradingAgents) 的标准架构设计。

## 目录结构

```
tradingagents/graph/
├── __init__.py              # 模块导出
├── trading_graph.py         # 主交易图
├── utils.py                 # 工具函数（LLM 初始化）
├── subgraphs/               # 子图模块
│   ├── __init__.py
│   ├── research_subgraph.py    # Research 子图（Bull/Bear 辩论）
│   └── risk_subgraph.py         # Risk 子图（Risky/Neutral/Safe 辩论）
└── README.md                # 本文档
```

## 主要组件

### 1. 主交易图 (`trading_graph.py`)

`create_trading_graph()` - 创建完整的交易决策图

**执行流程**：
1. Summary Nodes（串行）：market → news → sentiment → fundamentals
2. Research 子图：bull/bear 辩论 → research_manager
3. Trader：生成执行计划
4. Risk 子图：risky/neutral/safe 辩论 → risk_manager
5. 结束

### 2. 子图模块 (`subgraphs/`)

#### Research 子图
- **功能**：实现 Bull/Bear 研究辩论
- **流程**：bull → bear → bull → bear → research_manager → END
- **轮次**：固定 2 轮辩论（共 4 次发言）

#### Risk 子图
- **功能**：实现风险辩论
- **流程**：risky → neutral → safe → risky → neutral → safe → risk_manager → END
- **轮次**：固定 2 轮辩论（共 6 次发言）

### 3. 工具函数 (`utils.py`)

- `load_llm_from_config()` - 从配置文件加载 LLM（支持 Qwen，自动处理代理设置）

**注意**：Memory 类应该从数据库读取历史经验，不应使用 MockMemory。示例见 `run_graph_from_summary.py` 中的 `DatabaseMemory` 类。

## 使用示例

```python
from tradingagents.graph import create_trading_graph, load_llm_from_config
from tradingagents.agents.utils.memory_db_helper import MemoryDBHelper
from run_graph_from_summary import DatabaseMemory

# 加载 LLM
llm = load_llm_from_config()

# 创建 Memory（从数据库读取历史经验）
memory = DatabaseMemory(db_path="test.db", symbol="AAPL")

# 创建数据库连接
db_helper = MemoryDBHelper("test.db")

# 创建交易图
graph = create_trading_graph(
    llm=llm,
    memory=memory,
    data_manager=db_helper
)

# 准备初始状态
initial_state = {
    "company_of_interest": "AAPL",
    "trade_date": "2026-02-06",
    "trading_session": "pre_open",
    "messages": [],
}

# 运行图
for event in graph.stream(initial_state, stream_mode="updates"):
    for node_name, node_state in event.items():
        print(f"节点 {node_name} 执行完成")
```

## 架构设计

本模块遵循 TradingAgents 的标准架构：

1. **模块化设计**：主图和子图分离，便于维护和扩展
2. **条件边控制**：使用 `conditional_edges` 实现动态流程控制
3. **状态管理**：统一使用 `AgentState` 进行状态传递
4. **工具函数集中管理**：LLM 初始化、Memory 等工具函数统一管理

## 扩展指南

### 添加新的子图

1. 在 `subgraphs/` 目录创建新的子图文件
2. 实现子图的创建函数（如 `create_xxx_subgraph()`）
3. 在 `subgraphs/__init__.py` 中导出
4. 在主图 `trading_graph.py` 中集成

### 修改主图流程

编辑 `trading_graph.py` 中的 `create_trading_graph()` 函数，调整节点顺序和边连接。

## 参考

- [TradingAgents Graph API](https://opendeep.wiki/TauricResearch/TradingAgents/graph-api)
- [TradingAgents GitHub](https://github.com/TauricResearch/TradingAgents)

