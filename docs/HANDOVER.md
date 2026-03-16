# TradeSwarm 项目交接文档

> **创建日期**: 2026-02-10  
> **项目状态**: 核心功能已完成，可进行单标的和多标的回测  
> **最后回测**: NVDA 七日窗口 (2026-02-04 至 2026-02-12)，使用 memory.db 预置报告 + Silicon Flow LLM  
> **最后更新**: 2026-02-20

---

## 一、项目概述

### 1.1 项目目标

TradeSwarm 是一个基于多智能体（Multi-Agent）架构的 A 股市场交易决策系统，通过多智能体协作实现智能投资分析和决策。系统采用 LangGraph 框架构建，支持多种数据源接入，实现了模块化、可扩展的智能交易分析平台。

**核心设计目标**：
- 可连续自治运行数周/月
- 多智能体协作能力
- 长期记忆与自我稳定机制
- 完整的回测系统

### 1.2 技术栈

- **Python 3.12+**
- **LangChain 1.2.0** + **LangGraph 1.2.0**：工作流编排
- **SQLite** (`memory.db`) + **ChromaDB**：数据持久化
- **yfinance** + **Alpha Vantage**：数据源
- **Jinja2**：Prompt 模板化

### 1.3 当前状态

✅ **已完成的核心功能**：
- 完整的 Pre-Open 决策图（Summary → Research → Risk → Strategy → Trader）
- 单标的、多日回测驱动器
- 多标的、多周期回测脚本
- 每日交易摘要记录（`daily_trading_summaries`）
- 周期级反思代理（Reflector Agent）
- 多因子选股与再平衡
- 7 日滚动历史摘要维护

⚠️ **已知问题**：
- Alpha Vantage API 有访问限制（5 次/分钟，500 次/天）
- Market Open 执行逻辑在某些情况下可能不执行交易（需要调试）
- 部分分析师节点在 API 限制下可能失败

---

## 二、系统架构

### 2.1 完整交易流程（日级）

```text
┌─────────────────┐
│  Pre-Open 分析  │  ← 运行完整决策图（Summary → Research → Risk → Strategy → Trader）
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Market Open    │  ← 执行交易（每天最多一次）
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Post Close     │  ← 更新仓位、计算收益、保存 daily_summary
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ History Maintain│  ← 更新 7 日滚动摘要
└─────────────────┘
```

### 2.2 Pre-Open 决策图结构

```text
Summary 节点（串行）
  ├─ market_summary
  ├─ news_summary
  ├─ sentiment_summary
  └─ fundamentals_summary
         │
         ▼
Research 子图（2 轮辩论）
  ├─ Bull Researcher (Round 1)
  ├─ Bear Researcher (Round 1)
  ├─ Bull Researcher (Round 2)
  ├─ Bear Researcher (Round 2)
  └─ Research Manager
         │
         ▼
Risk 子图（2 轮辩论）
  ├─ Aggressive Debator (Round 1)
  ├─ Neutral Debator (Round 1)
  ├─ Conservative Debator (Round 1)
  ├─ Aggressive Debator (Round 2)
  ├─ Neutral Debator (Round 2)
  ├─ Conservative Debator (Round 2)
  └─ Risk Manager
         │
         ▼
Strategy Selector
  └─ 市场状态判断 + 策略选择
         │
         ▼
Trader
  └─ 交易方向 + 止盈止损
```

### 2.3 周期级流程（周/月）

```text
周期开始
    │
    ▼
┌─────────────────┐
│  选股与再平衡    │  ← StockSelector 选股 + PortfolioManager 调仓
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  每日交易循环    │  ← 对每个选中标的执行 Pre-Open → Market Open → Post Close
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Reflector      │  ← 周期结束：总结错误模式、成功模式、策略适用条件
└─────────────────┘
```

### 2.4 关键组件说明

#### Analyst（分析师）
- **设计原则**：并行运行、无状态、只分析不决策
- **已实现**：`market_analyst`、`news_analyst`、`sentiment_analyst`、`fundamentals_analyst`
- **数据存储**：原始报告存储在 `analyst_reports` 表，7 日滚动摘要存储在 `analyst_summaries` 表

#### Memory 系统
- **SQLite 数据库** (`memory.db`)：
  - `analyst_reports`：分析师原始报告
  - `analyst_summaries`：7 日滚动结构化摘要（技术、新闻、情绪、基本面）
  - `daily_trading_summaries`：每日交易摘要（市场状态、策略、收益等）
  - `cycle_reflections`：周期反思记录（错误模式、成功模式等）
- **ChromaDB**：`FinancialSituationMemory` 向量记忆（长期经验记忆）
- **History Maintainer**：自动维护 7 日滚动摘要

#### 决策模块（Pre-Open）
- **Research Manager**：整合四个 Analyst 摘要 + Bull/Bear 辩论，输出 `investment_plan`
- **Risk Manager**：基于 Research Plan + 风险辩论，输出风险约束和 `final_trade_decision`
- **Strategy Selector**：根据市场状态（`market_regime`）和风险决策，选择交易策略（`selected_strategy`）和预期行为（`expected_behavior`）
- **Trader**：根据策略选择，确定交易方向（BUY/SELL/HOLD）和止盈止损规则

#### 执行模块
- **Market Open**：执行交易决策，每天最多执行一次交易
- **Post Close**：更新持仓价格，计算日收益率和回撤，保存 `daily_trading_summary`
- **History Maintainer**：更新 7 日滚动摘要，供下一交易日使用

#### 周期级模块
- **Stock Selector**：多因子选股（动量、波动率、RSI、成交量、趋势强度），支持 IC 动态权重和市场状态权重
- **Portfolio Manager**：组合管理（持仓、现金、交易执行、再平衡）
- **Reflector Agent**：周期结束反思，总结错误模式、成功模式、策略适用条件，更新长期记忆

---

## 三、关键代码位置

### 3.1 主要运行脚本

| 脚本 | 路径 | 功能 |
|------|------|------|
| 单标的回测 | `run_single_symbol_backtest.py` | 单标的、多日回测（完整流程） |
| 多标的回测 | `run_multi_symbol_backtest.py` | 多标的、多周期回测（包含选股和调仓） |
| 周期反思 | `run_reflector_cycle.py` | 运行反思代理，总结周期内的交易经验 |

### 3.2 核心模块

#### 图定义
- **主交易图**：`tradingagents/graph/trading_graph.py`
- **Research 子图**：`tradingagents/graph/research_subgraph.py`
- **Risk 子图**：`tradingagents/graph/risk_subgraph.py`

#### Agent 节点
- **Analyst 节点**：
  - `tradingagents/agents/market_analyst/agent.py`
  - `tradingagents/agents/news_analyst/agent.py`
  - `tradingagents/agents/sentiment_analyst/agent.py`
  - `tradingagents/agents/fundamentals_analyst/agent.py`
- **Pre-Open 节点**：
  - `tradingagents/agents/pre_open/researchers/bull_researcher.py`
  - `tradingagents/agents/pre_open/researchers/bear_researcher.py`
  - `tradingagents/agents/pre_open/managers/research_manager/agent.py`
  - `tradingagents/agents/pre_open/managers/risk_manager/agent.py`
  - `tradingagents/agents/pre_open/managers/strategy_selector/agent.py`
  - `tradingagents/agents/pre_open/trader/trader.py`
- **执行节点**：
  - `tradingagents/agents/market_open/node.py`
  - `tradingagents/agents/post_close/node.py`
  - `tradingagents/agents/post_close/history_maintainer.py`
  - `tradingagents/agents/post_close/reflector.py`

#### 核心功能
- **数据适配器**：`tradingagents/core/data_adapter.py`
- **组合管理**：`tradingagents/core/portfolio/portfolio_manager.py`
- **选股器**：`tradingagents/core/selection/stock_selector.py`
- **策略库**：`tradingagents/core/strategies/strategy_lib.py`
- **数据库操作**：`tradingagents/agents/utils/memory_db_helper.py`

#### Prompt 模板
- 所有 Prompt 模板位于各 Agent 目录下的 `prompt.j2` 文件
- 例如：`tradingagents/agents/pre_open/trader/prompt.j2`

### 3.3 数据源

- **yfinance 提供者**：`datasources/data_sources/yfinance_provider.py`
- **Alpha Vantage 提供者**：`datasources/data_sources/alpha_vantage_provider.py`

### 3.4 状态管理

- **AgentState 定义**：`tradingagents/agents/utils/agentstate/agent_states.py`
- **状态字段说明**：
  - `today_report`：当日四位分析师报告
  - `history_report`：7 日滚动摘要
  - `past_memory_str`：长期经验记忆（向量检索）
  - `strategy_selection`：策略选择结果
  - `trader_plan`：交易员计划

---

## 四、数据库结构

### 4.1 表结构概览

#### `analyst_reports`
存储分析师原始报告。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| date | TEXT | 日期 |
| symbol | TEXT | 股票代码 |
| analyst_type | TEXT | 分析师类型（market/news/sentiment/fundamentals） |
| report_content | TEXT | 报告内容（JSON 字符串） |
| created_at | TIMESTAMP | 创建时间 |

#### `analyst_summaries`
存储 7 日滚动结构化摘要。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| date | TEXT | 日期 |
| symbol | TEXT | 股票代码 |
| market_summary | TEXT | 技术分析摘要（JSON 字符串） |
| news_summary | TEXT | 新闻摘要（JSON 字符串） |
| sentiment_summary | TEXT | 情绪摘要（JSON 字符串） |
| fundamentals_summary | TEXT | 基本面摘要（JSON 字符串） |
| created_at | TIMESTAMP | 创建时间 |

#### `daily_trading_summaries`
存储每日交易摘要。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| date | TEXT | 日期 |
| symbol | TEXT | 股票代码 |
| market_regime | TEXT | 市场状态 |
| selected_strategy | TEXT | 选择的策略 |
| expected_behavior | TEXT | 预期行为 |
| actual_return | REAL | 实际收益率 |
| actual_max_drawdown | REAL | 实际最大回撤 |
| positioning | TEXT | 仓位情况 |
| anomaly | TEXT | 异常情况 |
| summary_json | TEXT | 完整摘要（JSON 字符串） |
| created_at | TIMESTAMP | 创建时间 |

#### `cycle_reflections`
存储周期反思记录。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| cycle_type | TEXT | 周期类型（weekly/monthly） |
| cycle_start_date | TEXT | 周期开始日期 |
| cycle_end_date | TEXT | 周期结束日期 |
| symbol | TEXT | 股票代码（可选） |
| reflection_content | TEXT | 结构化反思内容（JSON 字符串） |
| key_insights | TEXT | 关键洞察 |
| error_patterns | TEXT | 错误模式 |
| success_patterns | TEXT | 成功模式 |
| strategy_conditions | TEXT | 策略适用条件 |
| environment_biases | TEXT | 环境判断偏差 |
| created_at | TIMESTAMP | 创建时间 |

### 4.2 数据库操作

使用 `MemoryDBHelper` 类进行数据库操作：

```python
from tradingagents.agents.utils.memory_db_helper import MemoryDBHelper

db_helper = MemoryDBHelper("memory.db")

# 查询分析师报告
reports = db_helper.query_analyst_reports(
    symbol="AAPL",
    start_date="2024-01-01",
    end_date="2024-01-31"
)

# 查询每日交易摘要
summaries = db_helper.query_daily_trading_summaries_by_date_range(
    symbol="AAPL",
    start_date="2024-01-01",
    end_date="2024-01-31"
)
```

详细说明请参考 `docs/数据库交互指南.md`。

---

## 五、使用指南

### 5.1 环境准备

```bash
# 安装环境
conda create -n TradeSwarm python=3.12
conda activate TradeSwarm
pip install -r requirements.txt

# 环境变量（.env 或 export）
# LLM：二选一或同时配置
export DASHSCOPE_API_KEY="your-api-key"           # 阿里 DashScope
export Silicon_API_KEY="your-silicon-key"         # Silicon Flow（可选）
export base_url_silicon="https://api.siliconflow.cn/v1"
export ALPHA_VANTAGE_API_KEY="your-alpha-vantage-key"

# 数据拉取需代理时（yfinance 等易被限速）
export USE_PROXY=true
export PROXY_HOST=127.0.0.1
export PROXY_PORT=7890
# 或直接设置 HTTP_PROXY / HTTPS_PROXY
```

**注意**：LLM 调用不能走代理，代码中会在创建 LLM 时临时清除代理环境变量；数据拉取前会根据 `USE_PROXY`/`PROXY_HOST` 恢复代理。

### 5.2 配置文件

创建 `config/config.yaml`（可选；LLM 也可仅靠 .env）：

```yaml
llm:
  api_key: ${DASHSCOPE_API_KEY}
  base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
  model_name: "qwen-plus"
  temperature: 0.1
  # Silicon Flow 可选（若配置了 Silicon_API_KEY，load_llm_from_config 会优先使用）
  silicon:
    api_key: ${Silicon_API_KEY}
    base_url: ${base_url_silicon}
    model_name: "Qwen/Qwen3-32B"
    temperature: 0.1

alpha_vantage:
  api_keys:
    - "your-api-key-1"
    - "your-api-key-2"
```

### 5.3 运行示例

#### 单标的回测

```bash
# 完整流程（每日调用 Analyst LLM + 决策 + 执行）
python run_single_symbol_backtest.py \
    --symbol NVDA \
    --start 2026-02-04 \
    --end 2026-02-12 \
    --cash 100000 \
    --db memory.db \
    --output backtest_results_nvda

# 仅用 memory.db 中已有报告，不调用 Analyst LLM（适合预构建数据集后快速回测）
python run_single_symbol_backtest.py \
    --symbol NVDA --start 2026-02-04 --end 2026-02-12 \
    --db memory.db --output backtest_results_7days \
    --use-db-reports-only
```

#### 多标的、多周期回测

```bash
python run_multi_symbol_backtest.py \
    --start_date 2024-01-01 \
    --end_date 2024-01-31 \
    --cycle_type monthly \
    --initial_cash 1000000 \
    --db_path memory.db \
    --output_dir backtest_results_cycle
```

#### 周期反思

```bash
python run_reflector_cycle.py \
    --cycle_type weekly \
    --start_date 2024-01-01 \
    --end_date 2024-01-07 \
    --symbol AAPL \
    --db_path memory.db
```

### 5.4 工具脚本

```bash
# 构建 Analyst 数据集（写入 memory.db，可选导出临时 JSON）
# 数据拉取走代理、LLM 不走代理；可用 --use-silicon 使用 Silicon Flow
python build_analyst_dataset.py --symbol NVDA --trading-days 7 --end 2026-02-13 --db memory.db --use-silicon
# 仅从 DB 导出 JSON（不调用 LLM）
python build_analyst_dataset.py --symbol NVDA --trading-days 7 --end 2026-02-13 --db memory.db --export-only

# 回测中途中断时，从已有 daily_results 聚合出 backtest_report.json
python aggregate_backtest_report.py --output-dir backtest_results_7days

# 运行 Analyst 并保存到数据库
python scripts/run_analysts_to_db.py

# 从摘要运行完整图
python scripts/run_graph_from_summary.py

# 导出数据库内容
python scripts/export_db_to_json.py
```

详细说明请参考 `docs/运行指南.md`。

---

## 六、最近回测结果示例

### 6.1 NVDA 回测（2025-11-06 至 2025-11-08）

**回测参数**：
- 标的：NVDA
- 日期范围：2025-11-06 至 2025-11-08
- 初始资金：100,000
- 输出目录：`backtest_results_nvda`

**结果摘要**：
- **交易日数**：2 天（11-06、11-07；11-08 为周六，非交易日）
- **总交易数**：0
- **最终净值**：100,000（无交易）

**详细结果**：
- **2025-11-06**：
  - 所有分析师报告生成成功
  - Pre-Open 完成：Trader 建议 BUY，Strategy Selector 选择 `trend_following`，Risk Manager 批准 BUY（仓位 30%）
  - Market Open 未执行交易（`market_open` 为空）
  - 最终无持仓

- **2025-11-07**：
  - fundamentals 和 sentiment 分析师遇到连接错误
  - Pre-Open 执行失败（因为连接错误）
  - 没有交易

**问题分析**：
- 11-06 虽然 Risk Manager 批准了 BUY，但 Market Open 没有执行交易，需要调试 `market_open/node.py` 的执行逻辑
- 11-07 因为 API 连接错误导致 Pre-Open 失败，需要处理 API 限制和错误重试

**结果文件位置**：
- 每日结果：`backtest_results_nvda/daily_results/YYYY-MM-DD.json`
- 回测报告：`backtest_results_nvda/backtest_report.json`

### 6.2 NVDA 七日回测（2026-02-04 至 2026-02-12）

**流程**：先由 `build_analyst_dataset.py` 为 NVDA 构建 7 个交易日的 Analyst 报告并写入 `memory.db`，再使用 `run_single_symbol_backtest.py --use-db-reports-only` 在相同窗口内跑决策与执行，不重复调用 Analyst LLM。

**回测参数**：
- 标的：NVDA
- 日期范围：2026-02-04 至 2026-02-12（7 个交易日）
- 初始资金：100,000
- 输出目录：`backtest_results_7days`
- LLM：Silicon Flow（Qwen/Qwen3-32B）用于 Pre-Open 决策；Analyst 报告来自 DB

**结果摘要**：
- 交易日数：6（与 daily_results 一致）
- 总收益/总交易：见 `backtest_results_7days/backtest_report.json`
- 若回测未跑完即中断，可用 `aggregate_backtest_report.py --output-dir backtest_results_7days` 从已有 daily_results 生成汇总报告。

---

## 七、已知问题与限制

### 7.1 API 访问限制

**问题描述**：
- Alpha Vantage API 有日访问限制（免费版通常为 5 次/分钟，500 次/天）
- 在运行选股和再平衡时，需要为多只股票获取数据，可能触发 API 限制

**影响范围**：
- `run_multi_symbol_backtest.py` - 多标的回测在选股阶段可能遇到限制
- Analyst 节点在 API 限制下可能失败

**解决方案**：
1. **使用缓存数据**：`DataAdapter` 已支持缓存，数据下载后会自动保存
2. **分批处理**：在选股时，可以分批获取数据，避免一次性请求过多
3. **使用本地数据**：如果有历史数据文件，可以直接使用
4. **等待时间**：在 API 限制之间添加适当的延迟

**临时处理**：
- 在 API 限制情况下，可以：
  - 使用较小的股票池进行测试（如 `STOCK_POOL[:20]`）
  - 使用已缓存的数据
  - 跳过选股测试，直接使用固定标的列表

详细说明请参考 `KNOWN_ISSUES.md`。

### 7.2 Market Open 执行问题

**问题描述**：
- 在某些情况下，即使 Risk Manager 批准了交易，Market Open 也可能不执行交易
- 从 NVDA 回测结果看，11-06 的 `market_open` 字段为空

**可能原因**：
1. 策略执行失败
2. 无法获取下一个交易日
3. 无法获取执行价格
4. 策略没有产生 BUY 信号

**需要调试**：
- 检查 `tradingagents/agents/market_open/node.py` 的执行逻辑
- 添加详细的日志输出，查看具体是哪个条件没有满足

### 7.3 其他问题

- **LLM 输出格式**：部分 LLM 输出可能不符合 JSON Schema，需要增强 JSON 提取逻辑
- **错误处理**：部分节点在遇到错误时可能没有优雅降级，需要增强错误处理

---

## 八、待办事项

### 8.1 已完成 ✅

- ✅ **单标的多日回测驱动器**：`run_single_symbol_backtest.py`
- ✅ **daily_trading_summaries 表**：每日交易摘要记录
- ✅ **标准化决策字段**：Strategy Selector 输出 `market_regime`、`selected_strategy`、`expected_behavior`
- ✅ **Market Open 执行逻辑**：交易执行、每天最多一次交易约束
- ✅ **Post Close 收益计算**：日收益率、回撤计算
- ✅ **周期级 Reflector Agent**：错误模式、成功模式总结
- ✅ **截面因子选股与再平衡**：多因子选股、IC 动态权重、市场状态权重
- ✅ **多标的、多周期持续运行脚本**：`run_multi_symbol_backtest.py`

### 8.2 待优化

- [ ] **集成 Analyst 节点到主图**：替代 Summary 节点直接查询，实现并行执行
- [ ] **子图执行优化**：考虑并行执行 Research 和 Risk 子图
- [ ] **策略库扩展**：添加更多交易策略
- [ ] **因子库扩展**：集成 Alpha101 因子库
- [ ] **实时监控**：系统监控面板、性能指标收集
- [ ] **可视化**：回测结果可视化、策略表现分析
- [ ] **Market Open 调试**：修复 Market Open 不执行交易的问题
- [ ] **API 错误处理**：增强 API 限制和错误重试机制

详细任务列表请参考 `Project_TODOs.md`。

---

## 九、开发规范

### 9.1 代码规范

- **类型注解**：所有函数、方法和类成员都必须有类型注解
- **文档字符串**：使用 Google 风格文档字符串
- **代码格式化**：使用 Ruff 进行代码格式化
- **测试覆盖**：使用 pytest 进行单元测试

### 9.2 架构原则

- **模块化设计**：每个模块/文件都应具有定义明确的单一职责
- **可复用组件**：开发可复用的函数和类，优先使用组合而非继承
- **状态管理**：使用统一的 `AgentState` TypedDict 管理状态
- **错误处理**：使用具体的异常类型，提供信息丰富的错误消息

### 9.3 Prompt 规范

- **模板化**：所有 Prompt 使用 Jinja2 模板（`.j2` 文件）
- **语言**：使用中文编写 Prompt
- **结构化输出**：使用 JSON Schema 约束 LLM 输出格式
- **上下文管理**：合理使用历史摘要和长期记忆

---

## 十、重要提示

### 10.1 环境变量

- LLM：`DASHSCOPE_API_KEY`（DashScope）或 `Silicon_API_KEY` + `base_url_silicon`（Silicon Flow）
- 数据拉取：需要代理时设置 `USE_PROXY=true` 及 `PROXY_HOST`/`PROXY_PORT`，或 `HTTP_PROXY`/`HTTPS_PROXY`
- Qwen/LLM 调用不能走代理，系统会在创建 LLM 时临时清除代理、数据拉取前恢复

### 10.2 数据库

- 使用 SQLite 数据库（`memory.db` 用于生产），会在首次运行时自动创建
- 数据库文件可能较大，建议定期备份

### 10.3 API 限制

- Alpha Vantage 有调用频率限制，系统已实现多 API Key 轮询机制
- 建议使用缓存数据，避免重复 API 调用

### 10.4 参考代码

- `trading_sys/` 目录包含参考代码（因子、策略、组合管理等）
- 实际使用的代码已集成到 `tradingagents/` 中，不应直接引用 `trading_sys/`

---

## 十一、相关文档

- [README.md](../README.md) - 项目主文档
- [docs/目录结构说明.md](目录结构说明.md) - 详细的目录结构说明
- [docs/运行指南.md](运行指南.md) - 系统运行指南
- [docs/数据库交互指南.md](数据库交互指南.md) - 数据库操作指南
- [docs/当前数据库表结构.md](当前数据库表结构.md) - 数据库表结构说明
- [Project_TODOs.md](../Project_TODOs.md) - 项目待办事项
- [KNOWN_ISSUES.md](../KNOWN_ISSUES.md) - 已知问题记录

---

## 十二、联系方式与支持

如有问题或需要进一步说明，请参考：
1. 项目文档（`docs/` 目录）
2. 代码注释和文档字符串
3. 已知问题记录（`KNOWN_ISSUES.md`）

---

---

## 十三、本次交接说明（2026-02-20）

### 13.1 本阶段完成内容

- **数据集构建**：`build_analyst_dataset.py` 支持按「最近 N 个交易日」生成 Analyst 报告，写入 `memory.db`，并可导出临时 JSON；支持 `--use-silicon` 使用 Silicon Flow，`--export-only` 仅从 DB 导出。
- **代理与 LLM 分离**：数据拉取（yfinance/交易日历）需代理时在 .env 中配置；LLM 初始化前临时清除代理环境变量，初始化后恢复，避免 LLM 走代理。
- **DataAdapter 时区修复**：yfinance 返回带时区 Index 与 naive 日期比较会报错，已在 `tradingagents/core/data_adapter.py` 中统一时区处理（见 `KNOWN_ISSUES.md`）。
- **memory.db 去重**：`MemoryDBHelper.insert_report_or_update` 按 (analyst_type, symbol, trade_date) 更新或插入，避免重复条；构建数据集时使用该方法。
- **回测从 DB 读报告**：`run_single_symbol_backtest.py` 增加 `--use-db-reports-only`，当日 Analyst 报告直接从 `memory.db` 读取，不调用 Analyst LLM，适合预构建数据集后的快速回测。
- **回测异常与聚合报告**：主循环包在 try/except 中，异常时仍会写入已完成的 daily_results 并生成 `backtest_report.json`；若中途中断未生成报告，可用 `aggregate_backtest_report.py --output-dir <dir>` 从已有 daily_results 聚合。
- **配置与文档**：`config/config.yaml` 可配置 Silicon Flow；`README.md` 精简并含流程图；`KNOWN_ISSUES.md` 记录 yfinance 时区问题与修复。

### 13.2 已移除的临时文件（本次整理）

- `test_spy_fetch.py`：单独测试 SPY 数据拉取与代理的脚本（诊断用，已删）。
- `analyst_dataset_*_temp.json`：构建数据集时导出的临时 JSON（已删；新导出会匹配 `.gitignore` 中的 `analyst_dataset_*_temp.json`）。

### 13.3 推荐实验流程（七日窗口示例）

1. **构建 7 日 Analyst 数据**（需代理 + LLM 可用）  
   `python build_analyst_dataset.py --symbol NVDA --trading-days 7 --end 2026-02-13 --db memory.db --use-silicon`
2. **回测（仅用 DB 报告，不重跑 Analyst）**  
   `python run_single_symbol_backtest.py --symbol NVDA --start 2026-02-04 --end 2026-02-12 --db memory.db --output backtest_results_7days --use-db-reports-only`
3. **查看收益**  
   查看 `backtest_results_7days/backtest_report.json`；若未生成则运行  
   `python aggregate_backtest_report.py --output-dir backtest_results_7days`

### 13.4 代码与文档位置速查

| 用途           | 位置 |
|----------------|------|
| 构建 Analyst 数据集 | `build_analyst_dataset.py` |
| 单标的回测（含 --use-db-reports-only） | `run_single_symbol_backtest.py` |
| 从 partial 结果聚合报告 | `aggregate_backtest_report.py` |
| LLM 加载（含 Silicon/代理处理） | `tradingagents/graph/utils.py` → `load_llm_from_config` |
| 报告写入/去重 | `tradingagents/agents/utils/memory_db_helper.py` → `insert_report_or_update` |
| 时区与数据拉取 | `tradingagents/core/data_adapter.py`；经验记录见 `KNOWN_ISSUES.md` |

---

**最后更新**: 2026-02-20  
**维护者**: TradeSwarm Team

