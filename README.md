# TradeSwarm

TradeSwarm 是一个基于 LangGraph 的多智能体投研与回测系统。

当前仓库已经按下面的使用模型重组：

- `data_prep`：手动准备本地回测所需数据
- `reporting`：消费已准备好的数据，产出人读报告和中间 Agent 过程
- `backtest`：消费同一套决策结果，导出结构化信号并运行 QuantConnect / Lean
- `experiments`：基于动态 `enabled_analysts` 做消融实验

系统默认支持动态 analyst 集合，例如：

- `market`
- `market,news`
- `market,news,sentiment,fundamentals`

## 快速开始

建议使用当前的 `langchain` 环境运行：

```powershell
python --version
```

请先确保以下内容已经准备好：

- `config/config.yaml`
- 仓库根目录下的 `.env`
- 本地数据库文件
- QuantConnect / Lean 本地环境

说明：

- 数据抓取阶段会使用代理设置
- LLM 阶段使用 Silicon Flow
- 回测执行由 QuantConnect / Lean 消费结构化信号，不直接消费原始分析文本

## 当前目录结构

```text
TradeSwarm/
├── apps/
│   ├── data_prep/
│   ├── reporting/
│   ├── backtest/
│   └── experiments/
├── tradingagents/
├── storage/
│   ├── db/
│   ├── market_data/
│   ├── reports/
│   ├── signals/
│   ├── backtests/
│   └── graph_dumps/
├── quantconnect/
├── lean_workspace/
└── scripts/
```

## 正式入口

### 1. Data Prep

这一步是手动执行的，不会自动串联。

#### 1.1 下载本地市场数据

```powershell
python apps\data_prep\download_market_data.py --help
```

#### 1.2 构建 `analyst_reports`

```powershell
python apps\data_prep\build_analyst_reports.py --help
```

当前该入口会转发到 [scripts/experimental/build_analyst_dataset.py](scripts/experimental/build_analyst_dataset.py)。

单个 analyst，单日：

```powershell
python apps\data_prep\build_analyst_reports.py --symbol NVDA --dates 2026-02-13 --db storage\db\memory.db --types market --only-missing --no-export
```

单个 analyst，多日区间：

```powershell
python apps\data_prep\build_analyst_reports.py --symbol NVDA --start 2025-02-01 --end 2025-03-01 --db storage\db\memory.db --types news --only-missing --no-export
```

单个 analyst，最近 N 个交易日：

```powershell
python apps\data_prep\build_analyst_reports.py --symbol NVDA --end 2026-02-13 --trading-days 5 --db storage\db\memory.db --types market --only-missing --no-export
```

两个 analyst：

```powershell
python apps\data_prep\build_analyst_reports.py --symbol NVDA --dates 2026-02-13,2026-02-14 --db storage\db\memory.db --types market,news --only-missing --no-export
```

常用参数：

- `--types`：指定 analyst 类型，支持 `market,news,fundamentals,sentiment`
- `--only-missing`：只补缺失或失败的报告
- `--skip-existing`：若指定类型已存在则跳过该交易日
- `--dates`：按显式日期列表构建
- `--no-export`：只写数据库，不导出临时 JSON

#### 1.3 构建 `analyst_summaries`

```powershell
python apps\data_prep\build_analyst_summaries.py --help
```

当前该入口会转发到 [scripts/experimental/run_history_maintainer_batch.py](scripts/experimental/run_history_maintainer_batch.py)。

单个 analyst，多日区间：

```powershell
python apps\data_prep\build_analyst_summaries.py --db storage\db\memory.db --symbol NVDA --start 2026-02-01 --end 2026-02-13 --types market --sleep-ms 500
```

两个 analyst，多日区间：

```powershell
python apps\data_prep\build_analyst_summaries.py --db storage\db\memory.db --symbol NVDA --start 2026-02-01 --end 2026-02-13 --types market,news --sleep-ms 500
```

单个 analyst，离散日期：

```powershell
python apps\data_prep\build_analyst_summaries.py --db storage\db\memory.db --symbol NVDA --dates 2026-02-10,2026-02-13 --types market --sleep-ms 500
```

行为说明：

- 不传 `--types`：处理全部 analyst summary
- 传了 `--types`：只处理指定 analyst summary
- 指定 analyst 缺少对应 report：跳过该 analyst，并继续后续任务

当前日志状态：

- `ok`：summary 已成功更新
- `skipped_existing`：summary 已存在，跳过
- `skipped_no_reports`：没有对应 source reports，跳过
- `error`：执行失败

### 2. Reporting

报告流默认消费已经准备好的 `analyst_reports` 和 `analyst_summaries`，并输出：

- `report.json`
- `report.txt`
- graph dump

```powershell
python apps\reporting\run_reports.py --help
```

单 analyst：

```powershell
python apps\reporting\run_reports.py --symbol NVDA --dates 2026-02-13 --db storage\db\memory.db --enabled-analysts market --experiment-id smoke_market_only --report-output-root storage\reports --graph-dump storage\graph_dumps
```

双 analyst：

```powershell
python apps\reporting\run_reports.py --symbol NVDA --dates 2026-02-13 --db storage\db\memory.db --enabled-analysts market,news --experiment-id smoke_market_news --report-output-root storage\reports --graph-dump storage\graph_dumps
```

### 3. Backtest

回测流会跑同一套 pre-open 决策流程，同时产出：

- 回测信号文件
- 日级报告文件
- graph dump

#### 3.1 只导出信号 / rating

```powershell
python apps\backtest\export_signals.py --help
```

底层核心脚本：

```powershell
python scripts\runtime\run_signal_export.py --help
```

单 analyst，rating：

```powershell
python apps\backtest\export_signals.py --symbol NVDA --dates 2026-02-13 --db storage\db\memory.db --output storage\signals --export-mode rating --enabled-analysts market --experiment-id smoke_market_only --report-output-root storage\reports --graph-dump storage\graph_dumps
```

单 analyst，backtest signal：

```powershell
python apps\backtest\export_signals.py --symbol NVDA --dates 2026-02-13 --db storage\db\memory.db --output storage\signals --export-mode backtest --enabled-analysts market --experiment-id smoke_market_only --report-output-root storage\reports --graph-dump storage\graph_dumps
```

为了缩短验证时间，可以临时覆盖辩论轮数：

```powershell
python apps\backtest\export_signals.py --symbol NVDA --dates 2026-02-13 --db storage\db\memory.db --output storage\signals --export-mode rating --enabled-analysts market --experiment-id smoke_market_only_fast --report-output-root storage\reports --graph-dump storage\graph_dumps --max-research-debate-rounds 1 --max-risk-debate-rounds 1
```

#### 3.2 一键自动回测

```powershell
python apps\backtest\run_backtest.py --help
```

底层脚本：

```powershell
python scripts\runtime\run_automated_backtest.py --help
```

示例：

```powershell
python apps\backtest\run_backtest.py --source export --symbol NVDA --db storage\db\memory.db --start 2026-02-01 --end 2026-02-13 --enabled-analysts market,news --experiment-id ablation_market_news --report-output-root storage\reports --graph-dump storage\graph_dumps
```

如果只想生成并复制信号，不实际执行 Lean：

```powershell
python apps\backtest\run_backtest.py --source export --symbol NVDA --db storage\db\memory.db --start 2026-02-01 --end 2026-02-13 --enabled-analysts market,news --experiment-id ablation_market_news --report-output-root storage\reports --graph-dump storage\graph_dumps --skip-backtest
```

### 4. Experiments

```powershell
python apps\experiments\run_ablation.py --help
```

示例：

```powershell
python apps\experiments\run_ablation.py --symbol NVDA --start 2026-02-01 --end 2026-02-13 --db storage\db\memory.db --enabled-analysts market,news --experiment-id ablation_market_news --max-research-debate-rounds 1 --max-risk-debate-rounds 1
```

## 运行产物

### 数据资产

- `storage\db\memory.db`
- `analyst_reports`
- `analyst_summaries`

### 报告资产

```text
storage/reports/<experiment_id>/<symbol>/<trade_date>/report.json
storage/reports/<experiment_id>/<symbol>/<trade_date>/report.txt
```

### 信号资产

```text
storage/signals/<experiment_id>/<symbol>/signals.json
storage/signals/<experiment_id>/<symbol>/ratings.json
```

### 图执行落盘

```text
storage/graph_dumps/<experiment_id>/<symbol>/<trade_date>/
```

### 回测结果

```text
storage/backtests/
```

## 动态 Analyst 说明

系统现在按 `enabled_analysts` 动态构造运行上下文:

- summary loader 按启用集合装配
- pre-open prompt 按启用集合组织上下文
- 报告和信号结果都会写入 `enabled_analysts`
- 消融实验可以直接比较不同 analyst 组合的结果

示例：

- `--enabled-analysts market`
- `--enabled-analysts market,news`
- `--enabled-analysts market,news,sentiment,fundamentals`

## Prompt 交付文档

中文版 prompt 工程需求文档：

- [docs/PROMPT_ENGINEERING_REQUIREMENTS.md](docs/PROMPT_ENGINEERING_REQUIREMENTS.md)

## 核心路径

| 功能 | 路径 |
|------|------|
| 报告流入口 | `apps/reporting/run_reports.py` |
| 回测流入口 | `apps/backtest/run_backtest.py` |
| report 构建入口 | `apps/data_prep/build_analyst_reports.py` |
| summary 构建入口 | `apps/data_prep/build_analyst_summaries.py` |
| Summary 装配 | `tradingagents/agents/pre_open/summary/loader.py` |
| Summary 注册表 | `tradingagents/agents/pre_open/summary/registry.py` |
| 主图 | `tradingagents/graph/trading_graph.py` |
| 信号导出 | `scripts/runtime/run_signal_export.py` |
| 自动回测 | `scripts/runtime/run_automated_backtest.py` |

## 当前注意事项

1. `apps/data_prep/build_analyst_reports.py` 和 `apps/data_prep/build_analyst_summaries.py` 当前仍是对旧脚本的转发壳，但已经是正式推荐入口。
2. `analyst_reports` 和 `analyst_summaries` 现在都支持 `--types`，可按单 analyst 或多 analyst 组合构建。
3. 默认辩论轮数下，完整 pre-open 流程耗时会明显增加；做 smoke test 时建议临时使用 `--max-research-debate-rounds 1 --max-risk-debate-rounds 1`。
4. 在当前环境里，仓库根目录下的 `memory.db` 可能出现 SQLite 只读问题，建议优先使用 `storage\db\memory.db`。
