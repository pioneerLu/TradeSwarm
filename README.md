# TradeSwarm

TradeSwarm 是一个基于多智能体（Multi-Agent）架构的 A 股市场交易决策系统，通过多智能体协作架构实现智能投资分析和决策。系统采用 LangGraph 框架构建，支持多种数据源接入，实现了模块化、可扩展的智能交易分析平台。

## 设计目标

TradeSwarm 是一个可**连续自治运行数周**、具备**多智能体协作能力**、拥有**长期记忆与自我稳定机制**的实验性研究框架。

---

## 当前实现架构

### 执行流程

```text
┌─────────┐
│  开始   │
└────┬────┘
     │
     ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────────┐     ┌───────────────────────┐
│ Market Summary  │ --> │  News Summary   │ --> │ Sentiment Summary   │ --> │ Fundamentals Summary  │
└────────┬────────┘     └────────┬────────┘     └──────────┬──────────┘     └───────────┬───────────┘
         │                       │                          │                              │
         └───────────────────────┴──────────────────────────┴──────────────────────────────┘
                                                              │
                                                              ▼
                                                    ┌──────────────────────┐
                                                    │  Research Subgraph   │
                                                    │  (Bull/Bear 辩论)    │
                                                    └───────────┬──────────┘
                                                                │
                                                                ▼
                                                    ┌──────────────────┐
                                                    │ Research Manager │
                                                    └─────────┬────────┘
                                                              │
                                                              ▼
                                                    ┌───────────────┐
                                                    │ Trader Node   │
                                                    └───────┬───────┘
                                                             │
                                                             ▼
                                                    ┌──────────────────┐
                                                    │  Risk Subgraph   │
                                                    │  (Risky/Neutral/ │
                                                    │  Conservative)   │
                                                    └─────────┬────────┘
                                                              │
                                                              ▼
                                                    ┌───────────────┐
                                                    │ Risk Manager  │
                                                    └───────┬───────┘
                                                            │
                                                            ▼
                                                    ┌───────────────┐
                                                    │     结束      │
                                                    └───────────────┘
```

### 技术实现

- **LangGraph 1.2.0** + LangChain：工作流编排
- **SQLite** (`memory.db` / `test.db`) + **ChromaDB**：数据持久化
- **yfinance** + **Alpha Vantage**：数据源
- 统一的 `AgentState` 状态管理
- **Jinja2**：Prompt 模板化

### 核心模块

#### Analyst（分析师）
- **设计原则**：并行运行、无状态、只分析不决策
- **已实现**：`market_analyst`、`news_analyst`、`sentiment_analyst`、`fundamentals_analyst`
- **待完善**：未集成到主交易图（现在使用 Summary 节点直接查询数据库）

#### Memory 系统
- **已实现**：
  - SQLite：`analyst_reports` 表，`MemoryDBHelper` 工具类
  - ChromaDB：`FinancialSituationMemory` 向量记忆
- **未实现**：Memory Controller（LLM 聚合历史报告生成摘要）

#### Manager（管理器）
- **Research Manager**：输入四个 Analyst 摘要 + 辩论，输出 `investment_plan`
- **Risk Manager**：输入 Research Plan + 风险辩论，输出 `final_trade_decision`（属于分析模块）
- **Trader**：输入 Research Plan，输出 `trader_investment_plan`

---

## 未来架构设计（时间驱动）

### 核心设计
开盘前分析 → 生成策略 → 开盘执行 → 盘中监控

### 关键设计点
- **分析模块**：Summary → Research → Trader → Risk（Risk Manager 属于分析模块）
- **时间路由**：`time_router` 节点 + `conditional_edge`，根据 `trading_session` 路由
- **策略持久化**：策略生成后保存到 `memory.db`（`trading_strategies` 表），作为历史经验
- **状态扩展**：`AgentState` 添加 `trading_session`、`trading_strategy`、`strategy_status` 等字段

---

## 项目目录结构

```
TradeSwarm/
├── config/                     # 配置文件目录
│   └── config.yaml            # 系统配置文件（LLM配置、数据源配置等）
├── datasources/               # 数据源模块
│   └── data_sources/          # 数据源提供者
│       ├── yfinance_provider.py
│       └── alphavantage_provider.py
├── tradingagents/             # 交易智能体模块
│   ├── agents/                # 智能体实现
│   │   ├── analysts/          # 分析师（Market/News/Fundamentals/Sentiment）
│   │   ├── pre_open/          # 开盘前分析模块
│   │   │   ├── summary/       # Summary 节点
│   │   │   ├── researchers/   # 研究员（Bull/Bear）
│   │   │   ├── managers/      # 管理器（Research/Risk）
│   │   │   ├── risk_mgmt/     # 风险辩论（Aggressive/Neutral/Conservative）
│   │   │   └── trader/        # 交易员
│   │   ├── market_open/       # 开盘执行模块（待实现）
│   │   ├── post_close/        # 收盘复盘模块（待实现）
│   │   ├── time_router/       # 时间路由节点
│   │   └── utils/             # 工具模块
│   │       ├── agentstate/    # AgentState 定义
│   │       ├── prompt_loader.py  # Prompt 模板加载器
│   │       └── memory_db_helper.py  # 数据库工具
│   ├── graph/                 # LangGraph 工作流
│   │   ├── trading_graph.py   # 主交易图
│   │   ├── utils.py           # 工具函数（LLM 加载）
│   │   └── subgraphs/         # 子图（Research/Risk）
│   └── tool_nodes/            # 工具节点
│       └── utils/             # 数据工具（market_tools, news_tools 等）
├── utils/                     # 工具模块
│   ├── config_loader.py       # 配置加载器
│   ├── data_utils.py          # 数据处理工具
│   └── llm_utils.py           # LLM工具函数
├── run_analysts_to_db.py      # 运行 Analyst 并保存到数据库
├── run_graph_from_summary.py  # 运行完整交易图
└── export_db_to_json.py       # 导出数据库内容
```

---

## 技术栈

### 核心技术
- **Python 3.12+**: 主要编程语言
- **LangChain 1.2.0**: 大语言模型应用开发框架
- **LangGraph 1.2.0**: 工作流编排框架
- **ChromaDB 1.3.7**: 向量数据库
- **SQLite**: 关系型数据库（`memory.db`）

### 数据源
- **yfinance**: 股票市场数据和历史行情
- **Alpha Vantage**: 新闻、基本面数据和财务指标

### 数据能力明细

| 指标名称 | 数据源 | 对应函数 | 简要说明 |
| :--- | :--- | :--- | :--- |
| **日线行情** | yfinance | `get_stock_data` | 获取历史日线数据（开高低收、成交量、涨跌幅等）|
| **技术指标** | yfinance | `get_indicators` | 获取 RSI、MACD、移动平均线等技术指标 |
| **公司信息** | Alpha Vantage | `get_company_info` | 获取公司基本信息、行业分类等 |
| **财务报表** | Alpha Vantage | `get_financial_statements` | 获取三大财务报表（利润表、资产负债表、现金流量表）|
| **财务指标** | Alpha Vantage | `get_financial_indicators` | 获取 ROE、ROA、毛利率等计算后指标 |
| **估值指标** | Alpha Vantage | `get_valuation_indicators` | 获取 PE、PB、市值等估值数据 |
| **业绩数据** | Alpha Vantage | `get_earnings_data` | 获取年度和季度业绩数据 |
| **公司新闻** | Alpha Vantage | `get_news` | 获取公司相关新闻（支持历史日期过滤）|
| **宏观新闻** | Alpha Vantage | `get_global_news` | 获取宏观经济新闻 |

---

## 使用方式

### 环境准备

```bash
# 安装环境
conda create -n TradeSwarm python=3.12
conda activate TradeSwarm
pip install -r requirements.txt

# 设置环境变量
export DASHSCOPE_API_KEY="your-api-key"
export ALPHA_VANTAGE_API_KEY="your-alpha-vantage-key"
```

### 配置文件

创建 `config/config.yaml`：

```yaml
llm:
  api_key: ${DASHSCOPE_API_KEY}
  base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
  model_name: "qwen-plus"
  temperature: 0.1

alpha_vantage:
  api_keys:
    - "your-api-key-1"
    - "your-api-key-2"
```

### 运行示例

```bash
# 1. 运行 Analyst 并保存到数据库
python run_analysts_to_db.py

# 2. 运行完整交易图（从 Summary 节点开始）
python run_graph_from_summary.py

# 3. 导出数据库内容
python export_db_to_json.py
```

---

## 开发规范

本项目遵循研究型代码开发规范，注重代码质量、文档完整性和系统可扩展性：

- **类型注解**：所有函数、方法和类成员都必须有类型注解
- **文档字符串**：使用 Google 风格文档字符串
- **代码格式化**：使用 Ruff 进行代码格式化
- **测试覆盖**：使用 pytest 进行单元测试

---

## TODO

### 结构相关

- [ ] **conditional_edge**：实现 `time_router` 节点 + `conditional_edge`，可能要修改 `AgentState`
- [ ] **策略生成节点**：整合 Research/Risk Manager 输出，生成结构化策略（JSON），保存到 `trading_strategies` 表
- [ ] **策略执行节点**：开盘时执行策略，盘中监控（止损/止盈），记录执行结果
- [ ] **Memory Controller**：实现 `MemoryController` 接口，LLM 聚合历史报告生成摘要
- [ ] **集成 Analyst 节点到主图**：替代 Summary 节点直接查询，实现并行执行
- [ ] **子图执行**：改成并行（待定）

### Prompt/Node 优化

- [ ] **Fusion Layer**：LLM 聚合多 Analyst 观点
- [ ] **Factor Layer**：因子计算模块，提取因子状态
- [ ] **Memory Consolidation**：合并相似结论，提炼长期 belief

### 交易平台相关

- [ ] **交易执行接口**：集成券商 API 或模拟交易
- [ ] **系统级反馈**：决策结果反向修正 memory 权重
- [ ] **策略回测集成**：Backtrader/VectorBT 集成
- [ ] **监控与日志**：系统监控面板、性能指标收集

---

## 版本历史

### v2.0 (2026-01-25)
- 完整的交易决策图实现（Summary → Research → Trader → Risk）
- Research 和 Risk 子图实现（辩论机制）
- SQLite 数据库集成（`analyst_reports` 表）
- 文件结构重构（`agentstate` 模块化）

### v1.0 (2025-12)
- 数据源集成（Tushare/AKShare）
- 基本面工具实现（AkShare 优先、Tushare 兜底）
- 分析师节点实现（Market/News/Sentiment/Fundamentals）

---

## Graph 架构说明

### 主交易图结构

主交易图 (`trading_graph.py`) 定义了完整的交易决策流程：

1. **Summary 节点**（串行执行）：
   - `market_summary` → `news_summary` → `sentiment_summary` → `fundamentals_summary`
   - 从数据库读取 Analyst 报告并生成摘要

2. **Research 子图**：
   - Bull/Bear 研究员进行 2 轮辩论
   - Research Manager 生成最终投资计划

3. **Trader 节点**：
   - 根据 Research Plan 生成执行计划

4. **Risk 子图**：
   - Risky/Neutral/Conservative 风险辩论者进行 2 轮辩论
   - Risk Manager 生成最终交易决策

### 子图设计

- **Research 子图**：固定 2 轮辩论（bull → bear → bull → bear → research_manager）
- **Risk 子图**：固定 2 轮辩论（risky → neutral → safe → risky → neutral → safe → risk_manager）
- 子图通过 `conditional_edge` 控制辩论轮次
- 子图状态自动合并到主图 `AgentState`

### 状态管理

- 所有节点共享 `AgentState` TypedDict
- 节点通过返回字典更新状态
- 子图的状态更新会自动传播到主图

详细技术实现请参考 `tradingagents/graph/` 目录下的代码。

---

## 注意事项

1. **环境变量**：需要设置 `DASHSCOPE_API_KEY` 和 `ALPHA_VANTAGE_API_KEY`
2. **数据库**：使用 SQLite 数据库（`test.db` 用于测试，`memory.db` 用于生产），会在首次运行时自动创建
3. **API 限制**：Alpha Vantage 有调用频率限制，系统已实现多 API Key 轮询机制
4. **Prompt 语言**：所有 Prompt 已模板化（Jinja2），使用中文编写
5. **LLM 代理**：Qwen LLM 不支持代理，系统会自动处理代理设置

---

**最后更新**: 2026-02-05  
**维护者**: TradeSwarm Team
