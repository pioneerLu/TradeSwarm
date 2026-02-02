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
- **SQLite** (`memory.db`) + **ChromaDB**：数据持久化
- **Tushare/AKShare**：数据源
- 统一的 `AgentState` 状态管理

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
│       ├── akshare_provider.py
│       └── tushare_provider.py
├── tradingagents/             # 交易智能体模块
│   ├── agents/                # 智能体实现
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
│   │       └── agentstate/    # AgentState 定义
│   └── graph/                 # LangGraph 工作流
│       └── pre_open/          # 开盘前交易图
│           ├── trading_graph.py
│           └── subgraphs/     # 子图（Research/Risk）
└── utils/                     # 工具模块
    ├── config_loader.py       # 配置加载器
    ├── data_utils.py          # 数据处理工具
    └── llm_utils.py           # LLM工具函数
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
- **Tushare Pro**: 专业的金融数据接口
- **AKShare**: 开源的金融数据接口

### 数据能力明细

| 指标名称 | 数据源 | 对应函数 | 简要说明 |
| :--- | :--- | :--- | :--- |
| **日线行情** | Tushare | `get_daily` | 获取历史日线数据（开高低收、成交量）|
| **每日指标** | Tushare | `get_daily_basic` | 获取每日收盘后的基本面指标（PE、PB、换手率等）|
| **实时盘口** | Tushare | `get_realtime_orderbook` | 获取实时五档买卖盘口及最新价 |
| **公司信息** | Tushare/AKShare | `get_company_info` | 获取单个公司的详细背景、主营业务等 |
| **财务报表** | Tushare/AKShare | `get_financial_statements` | 获取三大财务报表（利润表、资产负债表、现金流量表）|
| **财务指标** | Tushare/AKShare | `get_financial_indicators` | 获取 ROE、ROA、毛利率等计算后指标 |
| **估值指标** | AKShare | `get_valuation_indicators` | 获取盘中实时的 PE/PB 估值数据 |
| **业绩预告/快报** | Tushare/AKShare | `get_earnings_data` | 获取上市公司业绩预告/快报 |
| **宏观新闻** | AKShare | `get_macro_news` | 获取央视/百度财经等宏观新闻资讯 |
| **北向资金** | AKShare | `get_northbound_money_flow` | 获取沪深港通北向资金实时流向 |
| **全球指数** | AKShare | `get_global_indices_performance` | 获取美股、港股等全球核心指数涨跌幅 |
| **实时汇率** | AKShare | `get_currency_exchange_rate` | 获取美元兑人民币实时汇率 (USD/CNY) |

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
export TUSHARE_TOKEN="your-tushare-token"
```

### 配置文件

创建 `config/config.yaml`：

```yaml
llm:
  api_key: ${DASHSCOPE_API_KEY}
  base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
  model_name: "qwen-plus"
  temperature: 0.1
```

### 运行示例

```bash
# 运行完整交易图
python -m tradingagents.graph.pre_open.test_trading_graph

# 运行基本面分析师
python -m tradingagents.agents.pre_open.summary.fundamentals_summary.node
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

## 注意事项

1. **环境变量**：需要设置 `DASHSCOPE_API_KEY` 和 `TUSHARE_TOKEN`
2. **数据库**：使用 SQLite 数据库（`memory.db`），会在首次运行时自动创建
3. **API 限制**：Tushare 有调用频率限制，注意缓存机制
4. **Prompt 语言**：建议使用中文编写 prompt

---

**最后更新**: 2026-01-25  
**维护者**: TradeSwarm Team
