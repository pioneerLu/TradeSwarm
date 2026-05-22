# TradeSwarm

基于 LangGraph 的多智能体投研与回测系统。四条 pipeline 串联：

| Pipeline | 入口 | 作用 |
|----------|------|------|
| `data_prep` | `apps/data_prep/` | 市场数据、`analyst_reports` / `analyst_summaries` |
| `reporting` | `apps/reporting/` | 人读报告 + 可选 graph dump |
| `backtest` | `apps/backtest/` | 信号导出、批量 Lean、交错回测 |
| `experiments` | `apps/experiments/` | 按 `enabled_analysts` 消融 |

`enabled_analysts`：`market` → `market,news` → `market,news,sentiment,fundamentals`。

实验矩阵见 [exp.md](exp.md)。`storage/db/memory.db` 随仓库提交，其余 `storage/` 产物本地生成。

---

## 快速开始

```powershell
pip install -r requirements.txt
```

准备：`config/config.yaml`、`.env`（`Silicon_API_KEY`）、默认 DB `storage/db/memory.db`。回测需 Docker + `lean_workspace/`。

```powershell
python scripts\runtime\check_llm_config.py --llm-profile glm_4_6
python db_viewer\app.py --db storage\db\memory.db   # http://127.0.0.1:5555
```

## 目录结构

```text
apps/              # CLI 入口
tradingagents/     # 图、Agent、config、db
scripts/runtime/   # 回测、信号导出、交错回测
scripts/experimental/
datasources/  quantconnect/  db_viewer/  config/
storage/           # 报告/回测等本地产物（gitignored）；db/memory.db 随仓库提交
```

---

## 通用运行参数

report / signal export / 交错回测等入口共用：

| 参数 | 说明 |
|------|------|
| `--llm-profile` / `--llm-model` | SiliconFlow 模型；显式 profile 不存在时 fail-fast |
| `--strategy-skills-mode` | `reflect` \| `all` \| `off` |
| `--force-strategy-skill` | 强制注入 skill（消融） |
| `--current-position-pct` | rating 模式注入仓位比例 |
| `--max-research-debate-rounds` / `--max-risk-debate-rounds` | smoke test 建议 `1` |

---

## 1. Data Prep

```powershell
python apps\data_prep\download_market_data.py --help
python apps\data_prep\build_analyst_reports.py --help
python apps\data_prep\build_analyst_summaries.py --help
```

`build_analyst_reports` → [scripts/experimental/build_analyst_dataset.py](scripts/experimental/build_analyst_dataset.py)  
`build_analyst_summaries` → [scripts/experimental/run_history_maintainer_batch.py](scripts/experimental/run_history_maintainer_batch.py)

**analyst_reports**（`--types market,news,fundamentals,sentiment`，常用 `--only-missing --no-export`）：

```powershell
python apps\data_prep\build_analyst_reports.py --symbol NVDA --dates 2026-02-13 --db storage\db\memory.db --types market --only-missing --no-export
```

```powershell
python apps\data_prep\build_analyst_reports.py --symbol NVDA --start 2024-10-01 --end 2025-01-01 --db storage\db\memory.db --types fundamentals --only-missing --no-export
```

```powershell
python apps\data_prep\build_analyst_reports.py --symbol NVDA --end 2026-02-13 --trading-days 5 --db storage\db\memory.db --types market --only-missing --no-export
```

```powershell
python apps\data_prep\build_analyst_reports.py --symbol NVDA --dates 2026-02-13,2026-02-14 --db storage\db\memory.db --types market,news --only-missing --no-export
```

**analyst_summaries**：

```powershell
python apps\data_prep\build_analyst_summaries.py --db storage\db\memory.db --symbol NVDA --start 2024-10-01 --end 2025-01-01 --types sentiment --sleep-ms 500
```

```powershell
python apps\data_prep\build_analyst_summaries.py --db storage\db\memory.db --symbol NVDA --start 2026-02-01 --end 2026-02-13 --types market,news --sleep-ms 500
```

```powershell
python apps\data_prep\build_analyst_summaries.py --db storage\db\memory.db --symbol NVDA --dates 2026-02-10,2026-02-13 --types market --sleep-ms 500
```

---

## 2. Reporting

```powershell
python apps\reporting\run_reports.py --help
```

```powershell
python apps\reporting\run_reports.py --symbol NVDA --dates 2025-02-03 --db storage\db\memory.db --enabled-analysts market,news,sentiment,fundamentals --experiment-id report_only_nvda_20250203 --report-output-root storage\reports --graph-dump storage\graph_dumps
```

```powershell
python apps\reporting\run_reports.py --symbol NVDA --dates 2025-01-17 --db storage\db\memory.db --enabled-analysts market --experiment-id smoke_market_only --report-output-root storage\reports --graph-dump storage\graph_dumps --llm-profile glm_4_6 --current-position-pct 0.35
```

```powershell
python apps\reporting\run_reports.py --symbol NVDA --dates 2026-02-13 --db storage\db\memory.db --enabled-analysts market,news --experiment-id smoke_market_news --report-output-root storage\reports --graph-dump storage\graph_dumps
```

---

## 3. Backtest

### 3.1 信号 / rating 导出

```powershell
python apps\backtest\export_signals.py --help
```

```powershell
python apps\backtest\export_signals.py --symbol NVDA --dates 2026-02-13 --db storage\db\memory.db --output storage\signals --export-mode rating --enabled-analysts market --experiment-id smoke_market_only --report-output-root storage\reports --graph-dump storage\graph_dumps --llm-profile glm_4_6 --current-position-pct 0.35
```

```powershell
python apps\backtest\export_signals.py --symbol NVDA --dates 2026-02-13 --db storage\db\memory.db --output storage\signals --export-mode backtest --enabled-analysts market --experiment-id smoke_market_only --report-output-root storage\reports --graph-dump storage\graph_dumps
```

```powershell
python apps\backtest\export_signals.py --symbol NVDA --dates 2026-02-13 --db storage\db\memory.db --output storage\signals --export-mode rating --enabled-analysts market --experiment-id smoke_market_only_fast --report-output-root storage\reports --graph-dump storage\graph_dumps --max-research-debate-rounds 1 --max-risk-debate-rounds 1
```

### 3.2 批量自动回测

```powershell
python apps\backtest\run_backtest.py --help
```

```powershell
python apps\backtest\run_backtest.py --source export --symbol NVDA --db storage\db\memory.db --start 2026-02-01 --end 2026-02-13 --enabled-analysts market,news --experiment-id ablation_market_news --report-output-root storage\reports --graph-dump storage\graph_dumps
```

```powershell
python apps\backtest\run_backtest.py --source export --symbol NVDA --db storage\db\memory.db --start 2026-02-01 --end 2026-02-13 --enabled-analysts market,news --experiment-id ablation_market_news --report-output-root storage\reports --graph-dump storage\graph_dumps --skip-backtest
```

### 3.3 交错回测（Agent ↔ QC 逐日）

需 Docker、`lean_workspace/`、目标日期已有 `analyst_reports`（或 `--no-db-reports-only`）。产物：`storage/interleaved_backtests/` + `portfolio_snapshots`。

```powershell
python scripts\runtime\run_interleaved_backtest.py --help
```

```powershell
python scripts\runtime\run_interleaved_backtest.py --symbol NVDA --start 2025-01-02 --end 2025-02-28 --db storage\db\memory.db --initial-cash 100000
```

```powershell
python scripts\runtime\run_interleaved_backtest.py --symbol NVDA --start 2025-01-02 --end 2025-02-28 --db storage\db\memory.db --initial-cash 100000 --report-output-root storage\reports
```

```powershell
python scripts\runtime\run_interleaved_backtest.py --symbol NVDA --start 2025-01-01 --end 2025-03-01 --db storage\db\memory.db --enabled-analysts market,news,sentiment,fundamentals --max-research-debate-rounds 1 --max-risk-debate-rounds 1 --report-output-root storage\reports --graph-dump storage\graph_dumps -v --force-strategy-skill downtrend_skill
```

```powershell
python scripts\runtime\run_interleaved_backtest.py --symbol NVDA --start 2024-01-01 --end 2024-01-07 --db storage\db\memory.db --initial-cash 100000 --report-output-root storage\reports_2024 --graph-dump storage\graph_dumps -v
```

### 3.4 基准策略（BH / MA / MACD）

```powershell
python scripts\experimental\run_baseline_strategies_backtest.py --help
```

```powershell
python scripts\experimental\run_baseline_strategies_backtest.py --symbol NVDA --start 2024-01-01 --end 2024-03-01 --strategies "bh,ma"
```

PowerShell 下 `--strategies` 需加引号。产物目录：`storage/baseline_backtests/`。

---

## 4. Experiments

```powershell
python apps\experiments\run_ablation.py --help
```

```powershell
python apps\experiments\run_ablation.py --symbol NVDA --start 2026-02-01 --end 2026-02-13 --db storage\db\memory.db --enabled-analysts market,news --experiment-id ablation_market_news --max-research-debate-rounds 1 --max-risk-debate-rounds 1
```

---

## 运行产物（`storage/`）

| 类型 | 路径 |
|------|------|
| DB | `storage/db/memory.db` |
| 报告 | `storage/reports/<experiment_id>/<symbol>/<date>/report.{json,txt,html}` |
| 信号 | `storage/signals/<experiment_id>/<symbol>/signals.json` |
| 图 dump | `storage/graph_dumps/<experiment_id>/<symbol>/<date>/` |
| 交错回测 | `storage/interleaved_backtests/interleaved_<SYMBOL>_<ts>.{json,csv}` |
| QC 快照 | `lean_workspace/storage/snapshots/` |

---

## 开发参考

**改代码优先看**：

| 功能 | 路径 |
|------|------|
| 配置 | `tradingagents/config.py` |
| DB | `tradingagents/db/memory_db.py` |
| 主图 | `tradingagents/graph/trading_graph.py` |
| Summary | `tradingagents/agents/pre_open/summary/loader.py` |
| 信号导出 | `scripts/runtime/run_signal_export.py` |
| 交错回测 | `scripts/runtime/run_interleaved_backtest.py` |

`strategy_skills`（`config.yaml`：`reflect` / `all` / `off`）仅在 Trader prompt 内注入 skill，不改图拓扑。强制 skill 示例：

```powershell
python scripts\runtime\run_interleaved_backtest.py --symbol NVDA --start 2025-01-01 --end 2025-03-01 --strategy-skills-mode reflect --force-strategy-skill range_bound_skill
```

**约定**：仅通过 `apps/` 调用；`--use-db-reports-only` 时缺 report 的日期会跳过；交错回测每日启 Lean 容器，5 个交易日约 3–5 分钟。
