# TradeSwarm

基于多智能体架构的交易决策系统，采用 LangGraph 构建，支持连续自治运行、多智能体协作和长期记忆机制。

## 快速开始

```bash
# 1. 环境准备
conda create -n TradeSwarm python=3.12
conda activate TradeSwarm
pip install -r requirements.txt

# 2. 配置环境变量（.env 亦可）
# LLM：仅 Silicon Flow（见 config/config.yaml 的 llm.silicon；可多 key 见 docs/DATA_LAB.md）
export Silicon_API_KEY="your-silicon-key"
export base_url_silicon="https://api.siliconflow.cn/v1"
# 可选：export SILICON_MODEL="deepseek-ai/DeepSeek-V3.2"
export ALPHA_VANTAGE_API_KEY="your-alpha-vantage-key"
export FINANCIALDATA_API_KEY="your-financialdata-key"

# 3. 创建配置文件 config/config.yaml

# 4. 正式运行见下方；造数据与维护见 docs/DATA_LAB.md
```

**设计原则**：文本数据本地 + Agent 本地决策 + QuantConnect 仅做回测。

**入口脚本**：主流程在 `scripts/runtime/`；数据集与运维在 `scripts/experimental/`。仓库根目录同名 `.py` 为**薄封装**，与直接运行 `scripts/...` 等价。

## 核心流程命令（四步）

以下四条对应「数据进库 → 摘要进库 → Pre-Open 全图 → 平台回测」。**均在仓库根目录执行**（保证 `config/config.yaml`、`.env`、`memory.db` 路径一致）。

**「从 Summary 开始」的含义**：`trading_graph` 的入口是四个 Summary 节点（`market_summary` → … → `fundamentals_summary`）。它们从 `analyst_reports` 读**当日**报告；**历史窗口**优先读 `analyst_summaries`（第 2 步），若无则自动回退为拼接过去多日的原始报告。因此第 2 步为**可选但推荐**（上下文更短、更省 token）。

### 1. 构建 Analyst 报告写入 `memory.db`

功能与 CLI **已完备**（`scripts/experimental/build_analyst_dataset.py`）。

```bash
python scripts/experimental/build_analyst_dataset.py --symbol NVDA --start 2025-01-01 --end 2025-01-06 --db memory.db --only-missing --skip-existing
```

- 代理、LLM（仅 Silicon）、`--dates` / `--types` 等见 [docs/DATA_LAB.md](docs/DATA_LAB.md)。

### 2. 从已有报告生成 7 日滚动 Summary 写入 `analyst_summaries`

功能与 CLI **已完备**（`scripts/experimental/run_history_maintainer_batch.py`）。**不跑本步时 Pre-Open 仍可运行**，仅历史部分会改用原始报告拼接。

```bash
python scripts/experimental/run_history_maintainer_batch.py --db memory.db --symbol NVDA --start 2025-01-01 --end 2025-01-10 --sleep-ms 500
```

### 3. 从 Summary 起跑完整 Pre-Open（Research / Trader / Risk）并导出信号

**唯一推荐 CLI**：`scripts/runtime/run_signal_export.py`。默认 **`--use-db-reports-only`**：**不现场跑四个 Analyst**，仅使用 `analyst_reports` 里已有报告；**Pre-Open（Summary→Research→Trader→Risk）仍会调用 LLM**。最后 `resolve_signal` 写出 `qc_signals/signals.json`。

```bash
# 按区间（日历由 SPY 交易日推算）
python scripts/runtime/run_signal_export.py --symbol NVDA --start 2025-01-01 --end 2025-01-10 --db memory.db --output qc_signals
# 指定交易日并落盘 Pre-Open 节点输出（graph_outputs/ 已 gitignore）
python scripts/runtime/run_signal_export.py --symbol NVDA --dates 2025-01-13 --db memory.db --output qc_signals --graph-dump graph_outputs
```

- 仅导出评级、不要可执行信号：`--export-mode rating` → `ratings.json`。
- 多日注入模拟持仓（Trader/Risk 可见仓位）：`--simulate-portfolio [--initial-cash 100000]`。
- 需要现场造报告时再跑四分析师：`--no-db-reports-only`（费 API/LLM，一般先用 `build_analyst_dataset`）。
- **周期反思记忆**：本脚本内 `DatabaseMemory` 只读 `cycle_reflections`（周报）；无数据时记忆为空，属正常。

`scripts/experimental/run_graph_from_summary.py` **不再作为主入口维护**；请统一使用本脚本 `--dates` 或 `--start`/`--end`。

### 4. 在 QuantConnect / Lean 上跑回测（含第 3 步的一键串联）

**脚本逻辑已完备**（先导出/复制 `signals.json` 再 `lean backtest`），**前提是本机 Lean + Docker（或文档中的工作区布局）已按 [quantconnect/README.md](quantconnect/README.md) 配好**。

```bash
python scripts/runtime/run_automated_backtest.py --source export --symbol NVDA --db memory.db --start 2025-01-01 --end 2025-01-10
# 仅生成信号并复制到 quantconnect/signals/，不跑 lean：加 --skip-backtest
```

- 信号已有时也可用 `--source daily --daily-dir backtest_results/daily_results`（见下文「方式 C」）。

---

### 其它常用

```bash
python scripts/experimental/check_api_failures.py --symbol NVDA
python scripts/experimental/run_db_viewer.py
python scripts/runtime/run_reflector_cycle.py --symbol AAPL --cycle weekly --start 2024-01-01 --end 2024-01-07
```

更多参数与场景见 [docs/DATA_LAB.md](docs/DATA_LAB.md) 与 [quantconnect/README.md](quantconnect/README.md)。

---

## 一、信号导出与 QuantConnect 回测（方案 A）

Agent 生成交易信号，QuantConnect 执行回测并输出绩效报告。

**方式 A（定时）**：一键导出 + 复制 + `lean backtest`

```bash
python scripts/runtime/run_automated_backtest.py --source export --start 2025-01-01 --end 2025-03-01
# 或：python run_automated_backtest.py ...（根目录封装）
```

**方式 B**：仅导出（需 `memory.db` 含 `analyst_reports`），再复制 `qc_signals/signals.json` → `quantconnect/signals/`

```bash
python scripts/runtime/run_signal_export.py --symbol NVDA --start 2025-01-01 --end 2025-03-01 --db memory.db --output qc_signals
# 分析工具（仅评级，无 Portfolio / 无可执行信号）：加 --export-mode rating → 生成 qc_signals/ratings.json
# 多日导出时注入模拟仓（Trader/Risk 可见持仓）：加 --simulate-portfolio [--initial-cash 100000]
```

**方式 C**：从已有 `backtest_results/daily_results` 转换（无需 memory.db）

```bash
python scripts/runtime/run_automated_backtest.py --source daily --daily-dir backtest_results/daily_results
```

**QuantConnect / Lean**：云上步骤与本地 CLI 详见 [`quantconnect/README.md`](quantconnect/README.md)。

---

## 二、数据构建（造数据 / 维护）

构建与维护 `memory.db` 中的 **analyst_reports**、**analyst_summaries**，以及检查、去重、Web 查看等——**命令表与参数说明见 [docs/DATA_LAB.md](docs/DATA_LAB.md)**。

---

## 完整系统流程（方案 A）

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│  1. 数据构建（可选）                                                          │
│  build_analyst_dataset → analyst_reports                                     │
│  run_history_maintainer_batch → analyst_summaries                            │
└─────────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  2. 信号导出 run_signal_export.py                                            │
│  Analyst（DB/LLM）→ Pre-Open Graph → 信号解析器 → qc_signals/signals.json    │
└─────────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  3. QuantConnect 回测                                                        │
│  算法读取 signals.json → 每日开盘后按 execution_date 执行 BUY/SELL          │
│  → 平台输出绩效报告（收益、回撤、夏普等）                                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Pre-Open 决策图（内部）

```text
Summary（market/news/sentiment/fundamentals）→ Research 子图 → Trader → Risk 子图
→ 输出 trader_investment_plan, risk_summary
```

### 信号解析器

`tradingagents/agents/market_open/signal_resolver.py` 从 Pre-Open 输出解析出 `action`（BUY/SELL/HOLD）、`target_pct`、`entry_type`、`entry_price`、`execution_date` 等，供 QuantConnect 使用。

### 数据边界说明

除极简信号 JSON 外，**所有文本数据（报告、摘要、LLM 输出）均保留在本地**。

| 环节 | 位置 | 数据内容 | 是否上传/外传 |
|------|------|----------|---------------|
| 分析师报告 | 本地 `memory.db` | market/news/sentiment/fundamentals 原始报告 | 否 |
| 7 日摘要 | 本地 `memory.db` | `analyst_summaries` 表 | 否 |
| LLM 调用 | 本地 | Research/Trader/Risk 辩论与决策 | 否 |
| 交易结论 | 本地 `qc_signals/signals.json` | `action`, `target_pct`, `entry_type`, `entry_price`, `execution_date` 等 | 是，传入 QuantConnect |
| 行情数据 | QuantConnect | 由平台提供 | 否，仅平台内部使用 |
| 绩效报告 | QuantConnect | 收益、回撤、夏普等 | 平台生成并返回 |

QuantConnect 仅接收信号 JSON（操作类型、仓位比例、入场方式与价格、标的、执行日期），不包含任何分析原文或 LLM 输出。

---

## 核心模块（速查）

| 模块 | 说明 | 位置 |
|------|------|------|
| **Analyst** | 4 类分析师 | `tradingagents/agents/analysts/` |
| **Pre-Open 图** | LangGraph 决策流程 | `tradingagents/graph/trading_graph.py` |
| **信号解析器** | 解析可执行信号 | `tradingagents/agents/market_open/signal_resolver.py` |
| **History Maintainer** | 7 日滚动摘要 | `tradingagents/agents/post_close/history_maintainer.py` |
| **Memory** | SQLite + ChromaDB | `tradingagents/agents/utils/memory_db_helper.py` |
| **QuantConnect 算法** | 读取信号回测 | `quantconnect/main.py` |

**技术栈**：Python 3.12+ · LangGraph / LangChain · SQLite · ChromaDB · yfinance / Alpha Vantage · QuantConnect / Lean

## 项目结构

```
TradeSwarm/
├── tradingagents/          # 核心代码（agents / graph / core）
├── quantconnect/           # QC 算法与 signals/
├── qc_signals/             # 信号导出输出
├── scripts/
│   ├── runtime/            # 信号导出、自动回测、daily→signals、周期反思
│   ├── experimental/       # 造数据、检查、db_viewer、辅助脚本
│   └── *.ps1               # 如 run_lean_no_proxy.ps1
├── docs/                   # HANDOVER、DATA_LAB 等
├── db_viewer/              # Web 查看器包
├── run_*.py / build_*.py   # 根目录薄封装（转发到 scripts/）
└── requirements.txt
```

## 关键代码位置

| 功能 | 路径 |
|------|------|
| 信号导出 | `scripts/runtime/run_signal_export.py` |
| 信号解析 | `tradingagents/agents/market_open/signal_resolver.py` |
| Pre-Open 图 | `tradingagents/graph/trading_graph.py` |
| 数据适配器 | `tradingagents/core/data_adapter.py` |

## 文档索引

| 文档 | 说明 |
|------|------|
| [`docs/DATA_LAB.md`](docs/DATA_LAB.md) | 造数据、参数表、db_viewer、维护脚本 |
| `quantconnect/README.md` | QuantConnect / Lean 回测 |
| `docs/HANDOVER.md` | 项目交接 |
| `docs/IMPLEMENTATION_IDEAS.md` | 实现想法 |
| `KNOWN_ISSUES.md` | 已知问题 |
| `Project_TODOs.md` | 待办 |

## 注意事项

1. Alpha Vantage 免费版限流；造数据建议 `--only-missing`（见 DATA_LAB）。
2. 需 `config/config.yaml`；首次运行会创建 `memory.db`。
3. **LLM 仅 Silicon Flow**：`.env` 中配置 `Silicon_API_KEY`（及可选 `base_url_silicon`、`SILICON_MODEL`）；代理与数据拉取/LLM 分离见 [docs/DATA_LAB.md](docs/DATA_LAB.md)。

---

