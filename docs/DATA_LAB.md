# 数据构建与实验工具（DATA_LAB）

本文档聚焦数据准备、数据维护和实验辅助工具。

建议在仓库根目录执行所有命令，且优先使用可写数据库：

```text
storage/db/memory.db
```

所有示例均为 Windows 单行命令。

## 1. analyst_reports 构建

正式入口：

```powershell
D:\Software\Anaconda\envs\langchain\python.exe apps\data_prep\build_analyst_reports.py --help
```

当前该入口是正式参数入口，内部调用 `scripts/experimental/build_analyst_dataset.py`

### 常见用法

单个 analyst，单日：

```powershell
D:\Software\Anaconda\envs\langchain\python.exe apps\data_prep\build_analyst_reports.py --symbol NVDA --dates 2026-02-13 --db storage\db\memory.db --types market --only-missing --no-export
```

单个 analyst，多日区间：

```powershell
D:\Software\Anaconda\envs\langchain\python.exe apps\data_prep\build_analyst_reports.py --symbol NVDA --start 2026-02-01 --end 2026-02-13 --db storage\db\memory.db --types market --only-missing --no-export
```

单个 analyst，最近 N 个交易日：

```powershell
D:\Software\Anaconda\envs\langchain\python.exe apps\data_prep\build_analyst_reports.py --symbol NVDA --end 2026-02-13 --trading-days 5 --db storage\db\memory.db --types market --only-missing --no-export
```

两个 analyst：

```powershell
D:\Software\Anaconda\envs\langchain\python.exe apps\data_prep\build_analyst_reports.py --symbol NVDA --dates 2026-02-13,2026-02-14 --db storage\db\memory.db --types market,news --only-missing --no-export
```

导出临时 JSON：

```powershell
D:\Software\Anaconda\envs\langchain\python.exe apps\data_prep\build_analyst_reports.py --symbol NVDA --start 2026-02-01 --end 2026-02-13 --db storage\db\memory.db --types market --only-missing --output analyst_dataset_NVDA_market_temp.json
```

### 常用参数

| 参数 | 说明 |
|------|------|
| `--symbol` | 标的代码，默认 `NVDA` |
| `--start` / `--end` | 日期区间 |
| `--dates` | 离散日期列表，逗号分隔 |
| `--trading-days N` | 配合 `--end` 使用，取最近 N 个交易日 |
| `--types` | analyst 过滤，支持 `market,news,fundamentals,sentiment` |
| `--db` | SQLite 路径，建议使用 `storage\\db\\memory.db` |
| `--only-missing` | 只补缺失或失败报告 |
| `--skip-existing` | 如果指定 analyst 都已存在则跳过该日 |
| `--no-export` | 不导出临时 JSON，只写数据库 |
| `--output` | 导出临时 JSON 路径 |

## 2. analyst_summaries 构建

正式入口：

```powershell
D:\Software\Anaconda\envs\langchain\python.exe apps\data_prep\build_analyst_summaries.py --help
```

当前该入口是正式参数入口，内部调用 `scripts/experimental/run_history_maintainer_batch.py`

### 常见用法

单个 analyst，多日区间：

```powershell
D:\Software\Anaconda\envs\langchain\python.exe apps\data_prep\build_analyst_summaries.py --db storage\db\memory.db --symbol NVDA --start 2026-02-01 --end 2026-02-13 --types market --sleep-ms 500
```

两个 analyst，多日区间：

```powershell
D:\Software\Anaconda\envs\langchain\python.exe apps\data_prep\build_analyst_summaries.py --db storage\db\memory.db --symbol NVDA --start 2026-02-01 --end 2026-02-13 --types market,news --sleep-ms 500
```

单个 analyst，离散日期：

```powershell
D:\Software\Anaconda\envs\langchain\python.exe apps\data_prep\build_analyst_summaries.py --db storage\db\memory.db --symbol NVDA --dates 2026-02-10,2026-02-13 --types market --sleep-ms 500
```

全量 analyst：

```powershell
D:\Software\Anaconda\envs\langchain\python.exe apps\data_prep\build_analyst_summaries.py --db storage\db\memory.db --symbol NVDA --start 2026-02-01 --end 2026-02-13 --sleep-ms 500
```

### summary 构建行为

- 不传 `--types`：处理全部 analyst summary
- 传 `--types`：只处理指定 analyst summary
- 指定 analyst 缺少 source report：跳过该 analyst，不中断整批任务
- 如 summary 已存在：跳过，不重复调用 LLM

### summary 日志状态

| 状态 | 含义 |
|------|------|
| `ok` | summary 已成功更新 |
| `skipped_existing` | summary 已存在，跳过 |
| `skipped_no_reports` | 没有对应 source reports，跳过 |
| `error` | 执行失败 |

## 3. 报告与回测导出

### reporting

```powershell
D:\Software\Anaconda\envs\langchain\python.exe apps\reporting\run_reports.py --help
```

单 analyst：

```powershell
D:\Software\Anaconda\envs\langchain\python.exe apps\reporting\run_reports.py --symbol NVDA --dates 2026-02-13 --db storage\db\memory.db --enabled-analysts market --experiment-id smoke_market_only --report-output-root storage\reports --graph-dump storage\graph_dumps
```

### signal export

```powershell
D:\\Software\\Anaconda\\envs\\langchain\\python.exe apps\\backtest\\export_signals.py --help
```

单 analyst，rating：

```powershell
D:\\Software\\Anaconda\\envs\\langchain\\python.exe apps\\backtest\\export_signals.py --symbol NVDA --dates 2026-02-13 --db storage\\db\\memory.db --output storage\\signals --export-mode rating --enabled-analysts market --experiment-id smoke_market_only --report-output-root storage\\reports --graph-dump storage\\graph_dumps
```

单 analyst，backtest：

```powershell
D:\\Software\\Anaconda\\envs\\langchain\\python.exe apps\\backtest\\export_signals.py --symbol NVDA --dates 2026-02-13 --db storage\\db\\memory.db --output storage\\signals --export-mode backtest --enabled-analysts market --experiment-id smoke_market_only --report-output-root storage\\reports --graph-dump storage\\graph_dumps
```

快速 smoke test：

```powershell
D:\\Software\\Anaconda\\envs\\langchain\\python.exe apps\\backtest\\export_signals.py --symbol NVDA --dates 2026-02-13 --db storage\\db\\memory.db --output storage\\signals --export-mode rating --enabled-analysts market --experiment-id smoke_market_only_fast --report-output-root storage\\reports --graph-dump storage\\graph_dumps --max-research-debate-rounds 1 --max-risk-debate-rounds 1
```

## 4. 消融实验

正式入口：

```powershell
D:\Software\Anaconda\envs\langchain\python.exe apps\experiments\run_ablation.py --help
```

示例：

```powershell
D:\Software\Anaconda\envs\langchain\python.exe apps\experiments\run_ablation.py --symbol NVDA --start 2026-02-01 --end 2026-02-13 --db storage\db\memory.db --enabled-analysts market,news --experiment-id ablation_market_news --max-research-debate-rounds 1 --max-risk-debate-rounds 1
```

## 5. 其他常用工具

检查失败报告：

```powershell
D:\Software\Anaconda\envs\langchain\python.exe scripts\experimental\check_api_failures.py --symbol NVDA
```

查看数据库：

```powershell
D:\Software\Anaconda\envs\langchain\python.exe scripts\experimental\run_db_viewer.py
```

去重 analyst_reports：

```powershell
D:\Software\Anaconda\envs\langchain\python.exe scripts\experimental\dedupe_analyst_reports.py --db storage\db\memory.db
```

## 6. LLM 与代理说明

### LLM

当前数据构建与主流程均使用 Silicon Flow。

需要的环境变量通常包括：

- `Silicon_API_KEY`
- `base_url_silicon`
- `SILICON_MODEL`（可选）

### 代理

数据抓取阶段建议配置代理，例如：

- `USE_PROXY=true`
- `PROXY_HOST`
- `PROXY_PORT`

说明：

- 数据抓取阶段会使用代理
- LLM 请求默认直连
- 如果本地网络环境特殊，请按 `.env` 和当前代码逻辑调整

## 7. 当前注意事项

1. `apps/data_prep/build_analyst_reports.py`、`apps/data_prep/build_analyst_summaries.py` 和 `apps/data_prep/download_market_data.py` 现在都提供统一的正式参数入口，内部复用现有脚本实现。
2. `analyst_reports` 和 `analyst_summaries` 都支持 `--types`，可按单 analyst 或多 analyst 组合构建。
3. 默认辩论轮数下，完整 pre-open 流程耗时会明显增加；做 smoke test 时建议临时使用 `--max-research-debate-rounds 1 --max-risk-debate-rounds 1`。
4. 在当前环境里，仓库根目录下的 `memory.db` 可能出现 SQLite 只读问题，建议优先使用 `storage\\db\\memory.db`。
5. 本文档和 README 保持一致，若发现冲突，以 README 中的当前正式入口说明为准。


