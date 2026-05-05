# TradeSwarm

TradeSwarm 是一个基于 LangGraph 的多智能体投研与回测系统。

当前仓库按下面的功能构建：

- `data_prep`：手动准备本地回测所需数据
- `reporting`：消费已准备好的数据，产出人读报告和中间 Agent 过程
- `backtest`：消费同一套决策结果，导出结构化信号并运行 QuantConnect / Lean
- `experiments`：基于动态 `enabled_analysts` 做消融实验

系统默认支持动态 analyst 集合，例如：

- `market`
- `market,news`
- `market,news,sentiment,fundamentals`

**工作交接**：环境与架构要点、交错回测数据流、已知坑见 [docs/HANDOVER.md](docs/HANDOVER.md)。

## 快速开始

```powershell
pip install -r requirements.txt
```

请先确保以下内容已经准备好：

- `config/config.yaml`（从 `config/config.yaml.example` 复制并填入实际值）
- 仓库根目录下的 `.env`（配置 `Silicon_API_KEY` 等敏感信息）
- 本地数据库文件
- QuantConnect / Lean 本地环境（如需回测）

说明：

- 数据抓取阶段会使用代理设置
- LLM 阶段使用 Silicon Flow
- 回测执行由 QuantConnect / Lean 消费结构化信号，不直接消费原始分析文本

## 目录结构

```text
TradeSwarm/
├── pyproject.toml              # 包管理 + 依赖定义
├── config/
│   ├── config.yaml             # 运行时配置（gitignored）
│   └── config.yaml.example     # 配置模板
├── apps/                       # CLI 入口层（唯一推荐入口）
│   ├── data_prep/
│   ├── reporting/
│   ├── backtest/
│   └── experiments/
├── tradingagents/              # 核心包
│   ├── config.py               # 统一配置（YAML + .env + LLM 初始化）
│   ├── db/                     # 统一数据库访问层
│   ├── agents/                 # LLM Agent 节点
│   ├── core/                   # 数据适配器、策略、选股
│   ├── graph/                  # LangGraph 图定义
│   ├── tool_nodes/             # 分析师数据工具
│   └── dataflows/export/       # 信号导出
├── datasources/                # 数据源适配器
├── db_viewer/                  # Flask DB 查看器
├── quantconnect/               # QuantConnect 算法
├── storage/                    # 运行时数据资产
│   ├── db/
│   ├── market_data/
│   ├── reports/
│   ├── signals/
│   ├── backtests/
│   └── graph_dumps/
└── scripts/                    # 运维脚本（PowerShell + 实现逻辑）
```

## 正式入口

### 通用运行参数

以下参数在 report、signal export、交错回测入口中复用：

- `--llm-profile/--llm-model/--llm-temperature`：切换或覆盖 SiliconFlow 模型；产物 JSON 顶层会记录 `llm`。
- `--strategy-skills-mode reflect|all|off`：切换 Trader 动态 skill 注入方式；产物 JSON 顶层会记录 `strategy_skills`。
- `--strategy-skills-fallback-mode all|off`：`reflect` 模式下自反思输出无效时的降级策略。
- `--force-strategy-skill <skill>`：保留 `reflect` 自反思记录，但强制最终注入指定 skill，适合消融/压力测试。
- `--current-position-pct <0~1>`：仅分析/rating 模式使用，用于注入当前仓位比例。

`--llm-profile` 显式指定但配置不存在时会 fail-fast，避免模型对比实验误判。运行前可用下面命令检查最终 LLM 配置（不触网）：

```powershell
python scripts\runtime\check_llm_config.py --llm-profile glm_4_6
```

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
python apps\data_prep\build_analyst_reports.py --symbol NVDA --start 2024-10-01 --end 2025-01-01 --db storage\db\memory.db --types fundamentals --only-missing --no-export
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
python apps\data_prep\build_analyst_summaries.py --db storage\db\memory.db --symbol NVDA --start 2024-10-01 --end 2025-01-01 --types sentiment --sleep-ms 500
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
- `report.html`
- `report.pdf`（需安装 `weasyprint`；未安装时仍会生成 HTML）
- graph dump

```powershell
python apps\reporting\run_reports.py --help
```

模型、skill router、仓位注入等参数见上方“通用运行参数”。

只生成某一日的报告，不回测：

```powershell
python apps\reporting\run_reports.py --symbol NVDA --dates 2025-02-03 --db storage\db\memory.db --enabled-analysts market,news,sentiment,fundamentals --experiment-id report_only_nvda_20250203 --report-output-root storage\reports --graph-dump storage\graph_dumps
```

单 analyst：

```powershell
python apps\reporting\run_reports.py --symbol NVDA --dates 2025-01-17 --db storage\db\memory.db --enabled-analysts market --experiment-id smoke_market_only --report-output-root storage\reports --graph-dump storage\graph_dumps --llm-profile glm_4_6 --current-position-pct 0.35
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

模型、skill router、仓位注入等参数见上方“通用运行参数”。rating 模式会额外把 `--current-position-pct` 写入产物顶层 `input_position`。

单 analyst，rating：

```powershell
python apps\backtest\export_signals.py --symbol NVDA --dates 2026-02-13 --db storage\db\memory.db --output storage\signals --export-mode rating --enabled-analysts market --experiment-id smoke_market_only --report-output-root storage\reports --graph-dump storage\graph_dumps --llm-profile glm_4_6 --current-position-pct 0.35
```

单 analyst，backtest signal：

```powershell
python apps\backtest\export_signals.py --symbol NVDA --dates 2026-02-13 --db storage\db\memory.db --output storage\signals --export-mode backtest --enabled-analysts market --experiment-id smoke_market_only --report-output-root storage\reports --graph-dump storage\graph_dumps
```

为了缩短验证时间，可以临时覆盖辩论轮数：

```powershell
python apps\backtest\export_signals.py --symbol NVDA --dates 2026-02-13 --db storage\db\memory.db --output storage\signals --export-mode rating --enabled-analysts market --experiment-id smoke_market_only_fast --report-output-root storage\reports --graph-dump storage\graph_dumps --max-research-debate-rounds 1 --max-risk-debate-rounds 1
```

#### 3.2 一键自动回测（批量模式）

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

#### 3.3 Agent-QC 交错回测（Interleaved Mode）

交错模式逐日执行：Agent 生成当日信号 -> QC Lean 执行 -> 真实仓位回传 -> 下一天 Agent 基于真实持仓决策。

与批量模式相比，Agent 能感知限价单是否成交、实际滑点和真实 P&L。

底层脚本：

```powershell
python scripts\runtime\run_interleaved_backtest.py --help
```

模型和 skill router 参数见上方“通用运行参数”。交错回测汇总 `interleaved_*.json` 顶层会记录 `llm` 与 `strategy_skills`，保证结果可复现。

示例：

```powershell
python scripts\runtime\run_interleaved_backtest.py --symbol NVDA --start 2025-01-02 --end 2025-02-28 --db storage\db\memory.db --initial-cash 100000
```

如果希望同时落盘每日 `report.txt` / `report.json`，需要显式指定 `--report-output-root`（默认不落盘 report）：

```powershell
python scripts\runtime\run_interleaved_backtest.py --symbol NVDA --start 2025-01-02 --end 2025-02-28 --db storage\db\memory.db --initial-cash 100000 --report-output-root storage\reports
```

指定 analyst 组合和辩论轮数：

```powershell
python scripts\runtime\run_interleaved_backtest.py --symbol NVDA --start 2025-01-01 --end 2025-03-01 --db storage\db\memory.db --enabled-analysts market,news,sentiment,fundamentals  --max-research-debate-rounds 1 --max-risk-debate-rounds 1 --report-output-root storage\reports --graph-dump storage\graph_dumps -v --force-strategy-skill downtrend_skill
```

前提条件：

- Docker Desktop 已启动（Lean CLI 依赖 Docker）
- `lean_workspace/` 目录结构已就绪
- `analyst_reports` 已为目标日期范围准备好（或使用 `--no-db-reports-only` 即时生成）
- 交错回测会以 `lean_workspace/data/custom/<symbol>_daily.csv` 作为 Lean 执行主数据源（默认 `TS_LOCAL_DATA=1`）

交错回测产物保存在 `storage/interleaved_backtests/`，每日仓位快照同步写入 `memory.db` 的 `portfolio_snapshots` 表。
回测结束后会自动在同目录生成/追加以下产物：

- 汇总 JSON：`interleaved_<SYMBOL>_<timestamp>.json`
  - 顶层新增 `metrics`（含总收益率、年化/CAGR、Sharpe、Sortino、Calmar、最大回撤、胜率等）
  - 顶层新增 `daily_dates/daily_equity/daily_returns/cumulative_returns`（便于二次分析）
- 每日序列 CSV：`interleaved_<SYMBOL>_<timestamp>.csv`
  - 列：`date,equity,cumulative_return,daily_return,close_price`
- 图表：
  - `interleaved_<SYMBOL>_<timestamp>_return_vs_price.png`（策略收益 vs 标的涨跌幅）
  - `interleaved_<SYMBOL>_<timestamp>_equity_curve.png`（策略累计收益曲线）

落盘行为说明：

- 不传 `--report-output-root`：不会写每日 `report.txt` / `report.json`
- 不传 `--graph-dump`：不会写图节点输出和 `full_state_snapshot.json`
- 报告与图目录按 `experiment_id` 分组（由 `enabled_analysts` 推导或通过 `--experiment-id` 指定）
- 默认 `--use-db-reports-only` 下，若某日缺少 analyst report，会跳过该日，因此不会产出该日的新 report/graph dump

数据覆盖与自动补数行为：

- 回测开始前会先检查 `lean_workspace/data/custom/<symbol>_daily.csv` 是否覆盖本次交易日
- 若覆盖不足，脚本会自动调用 `scripts/runtime/download_yf_for_lean.py` 下载并覆盖同一路径
- 下载后会再次校验；若仍有缺失日期，流程会直接终止（fail-fast），避免输出大量 `null` 快照
- 汇总 JSON 顶层会写入 `data_coverage` 与 `snapshot_coverage` 字段，便于判断结果可信度

```powershell
python scripts\runtime\run_interleaved_backtest.py --symbol NVDA --start 2024-01-01 --end 2024-03-01 --db storage\db\memory.db --initial-cash 100000 --report-output-root storage\reports_2024 --graph-dump storage\graph_dumps -v
```

#### 3.4 基准策略对比回测（BH / MA / MACD）

该脚本用于在同一时间区间内，跑三类**规则基准**策略（Buy&Hold / MA Cross / MACD）以便与 Agent/交错回测做对比。

入口脚本：

```powershell
python scripts\experimental\run_baseline_strategies_backtest.py --help
```

示例（对比 BH 与 MA，并绘制权益曲线图）：

```powershell
conda run -n langchain python scripts\experimental\run_baseline_strategies_backtest.py --symbol NVDA --start 2024-01-01 --end 2024-03-01 --strategies "bh,ma"
```

产物：

- 汇总 JSON：`storage/baseline_backtests/baseline_<SYMBOL>_<timestamp>.json`
  - 每个策略包含 `metrics`（含总收益率、年化/CAGR、Sharpe、Sortino、Calmar、最大回撤、胜率等）
  - 每个策略包含 `daily`（逐日权益、shares、cash 等）
- 每日序列 CSV（每策略一份）：`baseline_<SYMBOL>_<timestamp>_<strategy>.csv`
  - 可用 `--export-csv-dir <目录>` 指定导出目录（默认与 JSON 同目录）
  - 列：`date,equity,cumulative_return,daily_return,close_price`
- 权益曲线图：同目录 `baseline_<SYMBOL>_<timestamp>_equity_curves.png`（需要 `matplotlib`；否则可加 `--no-plot`）

注意：

- PowerShell 下 `--strategies` 建议加引号，例如 `--strategies "bh,ma"`（避免被拆成多个参数）。
- 数据抓取走 `DataAdapter`/`yfinance` 时可能触发限流，必要时按 `tradingagents/core/data/loader.py` 的方式设置代理（`PROXY_HOST/PROXY_PORT` + `--use-proxy`）。

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
- `portfolio_snapshots`（交错回测产生的每日真实仓位快照）

### 报告资产

```text
storage/reports/<experiment_id>/<symbol>/<trade_date>/report.json
storage/reports/<experiment_id>/<symbol>/<trade_date>/report.txt
storage/reports/<experiment_id>/<symbol>/<trade_date>/report.html
storage/reports/<experiment_id>/<symbol>/<trade_date>/report.pdf
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
storage/interleaved_backtests/    # 交错回测最终汇总
lean_workspace/storage/snapshots/ # QC Object Store 每日快照（JSON）
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

## Prompt 内部动态 Skill Router

不新增 agent，不改变 LangGraph/pipeline。默认 `strategy_skills.mode=reflect` 时，Trader 节点内部先做一次市场状态自反思，再只注入选中的 skill 模板生成最终交易 JSON；Risk Manager 不额外自反思，只复核 Trader 的选择。

`config.yaml` 支持：

```yaml
strategy_skills:
  mode: reflect        # reflect | all | off
  fallback_mode: off   # all | off
  force_skill: null    # 可选：strong_uptrend_skill | range_bound_skill | downtrend_skill | high_vol_uncertain_skill
```

模式：

- `reflect`：Trader 自反思后只注入一个 skill。
- `all`：全量注入四个 skill，作为对照实验。
- `off`：不注入 skill，仅依赖模型自身判断。

四类 skill：`strong_uptrend_skill`、`range_bound_skill`、`downtrend_skill`、`high_vol_uncertain_skill`。如需强制注入某个 skill，可传：

```powershell
python scripts\runtime\run_interleaved_backtest.py --symbol NVDA --start 2025-01-01 --end 2025-03-01 --strategy-skills-mode reflect --force-strategy-skill range_bound_skill
```

最终 signal 会记录 Risk/Trader 最终 regime 字段，以及 Trader 第一段自反思的 `skill_router_mode/reflection_*` 字段；强制覆盖时额外记录 `forced_selected_skill`。交错回测 `daily_results` 和 CSV 也会同步记录。

## 核心路径

| 功能 | 路径 |
| --- | --- |
| 统一配置 | `tradingagents/config.py` |
| 统一 DB 层 | `tradingagents/db/` |
| 报告流入口 | `apps/reporting/run_reports.py` |
| 回测流入口 | `apps/backtest/run_backtest.py` |
| report 构建入口 | `apps/data_prep/build_analyst_reports.py` |
| summary 构建入口 | `apps/data_prep/build_analyst_summaries.py` |
| Summary 装配 | `tradingagents/agents/pre_open/summary/loader.py` |
| Summary 注册表 | `tradingagents/agents/pre_open/summary/registry.py` |
| 主图 | `tradingagents/graph/trading_graph.py` |
| 信号导出 | `scripts/runtime/run_signal_export.py` |
| 自动回测（批量） | `scripts/runtime/run_automated_backtest.py` |
| 交错回测 | `scripts/runtime/run_interleaved_backtest.py` |
| Lean 结果解析 | `tradingagents/core/lean_result_parser.py` |
| 仓位格式化工具 | `tradingagents/agents/utils/state_helpers.py` |
| Portfolio Snapshots DB | `tradingagents/db/memory_db.py` (portfolio_snapshots) |

## 交错回测架构

系统回测模式：

**交错模式**：逐日交替执行 Agent 决策与 QC 回测，真实仓位反馈到下一天的 Agent。流程如下：

```text
Day 1: Agent(空仓) -> signal -> QC执行 -> 真实持仓(144股, $138.31成交)
Day 2: Agent(知道持144股) -> signal -> QC执行 -> 真实持仓(限价单未成交, 仍144股)
Day 3: Agent(知道限价单没成交) -> signal -> ...
```

所有 Agent 节点（包括 bull/bear researcher、risky/neutral/conservative debator、trader、risk manager）均可感知当前仓位状态。`signal_resolver` 使用完整仓位信息进行增量仓位计算和重复建仓守卫。

## 注意事项

1. `apps/` 是唯一推荐的 CLI 入口层。根目录下的旧 `run_*.py` shim 已删除。
2. `analyst_reports` 和 `analyst_summaries` 支持 `--types`，可按单 analyst 或多 analyst 组合构建。
3. 默认辩论轮数下，完整 pre-open 流程耗时会明显增加；做 smoke test 时建议临时使用 `--max-research-debate-rounds 1 --max-risk-debate-rounds 1`。
4. 建议使用 `storage\db\memory.db` 作为数据库路径。
5. 交错回测每天需启动一次 Docker 容器运行 Lean，5 个交易日约需 3-5 分钟（主要开销在 Docker 启停）。
