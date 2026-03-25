# 数据构建与实验工具（DATA_LAB）

在仓库根目录执行；相对路径（如 `memory.db`、`qc_signals/`）均相对于**仓库根**。

**推荐路径**：脚本位于 `scripts/experimental/`；根目录同名文件为薄封装，等价于调用下方命令。

---

## Analyst 报告（`analyst_reports`）

| 操作 | 命令示例 |
|------|----------|
| 指定日期构建 | `python scripts/experimental/build_analyst_dataset.py --symbol NVDA --dates 2025-02-12 --db memory.db --no-export` |
| 按区间构建（实验区间示例） | `python scripts/experimental/build_analyst_dataset.py --symbol NVDA --start 2025-01-01 --end 2025-03-01 --db memory.db` |
| 仅构建某一类（如 market） | `python scripts/experimental/build_analyst_dataset.py --symbol NVDA --start 2025-01-01 --end 2025-03-01 --types market --db memory.db` |
| 仅构建多类 | `--types market,news`（逗号分隔：`market,news,fundamentals,sentiment`） |
| 仅补全缺失/失败报告（省 API） | 同上，加 `--only-missing` |
| 按失败日补全报告 | 先 `check_api_failures`，再对报告中的日期执行 `build_analyst_dataset.py --dates YYYY-MM-DD --only-missing --no-export`（多日可用逗号分隔 `--dates`） |
| 检查失败报告 | `python scripts/experimental/check_api_failures.py`（输出写入仓库根 `api_failures_report.txt`） |

**完整参数样例（仅构建 market，实验区间）**：

```bash
python scripts/experimental/build_analyst_dataset.py --symbol NVDA --start 2025-01-01 --end 2025-03-01 --types market --db memory.db --only-missing --skip-existing --output analyst_dataset_NVDA_2025Q1_market_temp.json
```

| 参数 | 说明 |
|------|------|
| `--symbol` | 标的，默认 `NVDA` |
| `--start` / `--end` | 区间起止（与 `--dates` / `--trading-days` 互斥，见脚本 `--help`） |
| `--types market` | 只跑 Market Analyst（yfinance）；多类用 `market,news` |
| `--db` | SQLite 路径，默认 `memory.db` |
| LLM 后端 | **仅 Silicon Flow**：`.env` 中 `Silicon_API_KEY`、`base_url_silicon`（可选）、`SILICON_MODEL`（可选）；`build_analyst_dataset` 固定 `create_silicon_llm`；`load_llm_from_config` / Chroma 亦只读 Silicon（`tradingagents/llm_env_compat.py`）。已移除 `--use-silicon` 与自定义 `API_KEY`/`base_url` 主线路。 |
| `--only-missing` | 仅补「无报告或判定为 API 失败」的条目，省调用 |
| `--skip-existing` | 若当日所选类型均已存在则跳过该日 |
| `--output` | 导出合并 JSON；若只要写库可加 `--no-export` 省略导出 |
| `--dates` | 逗号分隔单日，如 `--dates 2025-01-07`，会忽略 `--start`/`--end` |
| `--trading-days N` | 与 `--end` 联用，取最近 N 个交易日 |

数据拉取建议 `.env` 配置 `USE_PROXY=true` 与 `PROXY_HOST`/`PROXY_PORT`；脚本会在数据阶段走代理、LLM 直连。

### `build_analyst_dataset`：LLM 备用 API（限速故障转移）

仅在本脚本内生效：主 LLM 为 **Silicon Flow**（`create_silicon_llm`）；若触发 **限速、超时、连接错误、服务端 5xx** 等，可自动改用 **备用 OpenAI 兼容端点** 再试（LangChain `with_fallbacks`，见下表）；多 Silicon key 时亦可主备都在 Silicon。

在 `.env` 中配置（三项均必填才会启用）：

| 变量 | 说明 |
|------|------|
| `LLM_FALLBACK_API_KEY` | 备用网关 API Key |
| `LLM_FALLBACK_BASE_URL` | 备用网关 Base URL（与主线路同一 OpenAI 兼容协议，如另一 Silicon 兼容网关或自建 `/v1`） |
| `LLM_FALLBACK_MODEL` | 备用线路上的模型名 |
| `LLM_FALLBACK_TEMPERATURE` | 可选，默认 `0.1` |

示例：主线路为默认 Silicon；备用品为另一 OpenAI 兼容服务时，将备用三件套设为该服务的 key / base_url / model。

另外，若你两条线路都在 Silicon，可直接把 `Silicon_API_KEY` 配成**列表或逗号分隔**，脚本会自动按顺序故障转移，例如：

```env
Silicon_API_KEY=["sk-key-1","sk-key-2"]
# 或
Silicon_API_KEY=sk-key-1,sk-key-2
```

### 运行「卡住」或长时间无输出

`build_analyst_dataset` 会在终端打印 `[数据] 拉取交易日历...`、以及每个 Analyst 的 `[LLM] 开始 xxx @ 日期`。若长时间停在某一类：

| 变量 / 参数 | 含义 | 默认 |
|-------------|------|------|
| `LLM_HTTP_READ_TIMEOUT` | 单次 LLM 请求读超时（秒） | `120` |
| `LLM_HTTP_CONNECT_TIMEOUT` | TCP 连接超时（秒） | `15` |
| `LLM_MAX_RETRIES` | OpenAI 兼容客户端自动重试次数 | `0`（避免失败后反复重试显得「卡住」） |
| `--llm-read-timeout SEC` | 命令行覆盖读超时 | 与上表等价 |

若卡在 `[数据] 拉取交易日历`，多为 **yfinance / 代理** 问题，可检查 `USE_PROXY`、`PROXY_HOST/PORT` 或暂时关闭代理试跑。

> **首次**区间内全量生成 market：可去掉 `--only-missing`、`--skip-existing`，并视需要加 `--no-export` 不写临时 JSON。

---

## Pre-Open 图：辩论轮次（`config/config.yaml`）

`scripts/runtime/run_signal_export.py` 等使用的 LangGraph 中，牛熊与风险辩论的轮数可由配置调整。**增大轮数会近似线性增加 LLM 调用次数与费用。**

| 配置项 | 含义 | 默认 |
|--------|------|------|
| `graph.max_research_debate_rounds` | 研究侧「轮数」；每轮含 bull、bear 各 1 次发言 | `2` |
| `graph.max_risk_debate_rounds` | 风险侧「轮数」；每轮含 risky、neutral、safe 各 1 次 | `2` |

结束条件：研究侧当 `investment_debate_state.count >= max_research_debate_rounds * 2` 时进入 `research_manager`；风险侧当 `risk_debate_state.count >= max_risk_debate_rounds * 3` 时进入 `risk_manager`。代码中轮数会被限制在 1～20。

---

## 信号导出：QuantConnect 回测 vs 分析评级（方案 2a）

主入口：`scripts/runtime/run_signal_export.py`（配置固定读仓库 `config/config.yaml`）。**默认 `--use-db-reports-only`**：只要求库里已有当日四类 `analyst_reports`，不现场跑四分析师；**Pre-Open 全图仍会调 LLM**。`--no-db-reports-only` 改为每日现场跑四分析师写库。`--dates D1,D2,...` 时仅处理列出日期，不再用 `--start`/`--end` 推日历。

| 模式 | 命令要点 | 输出文件 | 说明 |
|------|----------|----------|------|
| 回测（默认） | `python scripts/runtime/run_signal_export.py ...` | `qc_signals/signals.json` | 调用 `resolve_signal`，含 `action` / `target_pct` / `execution_date` 等，供 QC 执行 |
| 指定交易日 | 加 `--dates 2025-01-02,2025-01-03` | 同上 | 可与 `--export-mode` / `--simulate-portfolio` 组合 |
| 分析评级 | 同上，加 `--export-mode rating` | `qc_signals/ratings.json` | **不注入** `current_position` / `portfolio_state`，**不调用** `resolve_signal`；仅抽取 `research_decision` 与 Risk 的 `fine_rating` / `final_decision` / `risk_level` |
| 回测 + 模拟仓 | 加 `--simulate-portfolio`（可选 `--initial-cash`） | 仍为 `signals.json` | 多日循环用 [`tradingagents/core/portfolio_simulator.py`](e:/agent_proj/TradeSwarm/tradingagents/core/portfolio_simulator.py) 注入组合状态，使 Trader / risk_manager 与 `is_holding` 对齐；**research_manager 仍不接持仓** |

**记忆**：脚本中 `DatabaseMemory` 仅从 `cycle_reflections`（周报）注入反思；表空时无记忆，不影响导出。

---

## History Summary（`analyst_summaries`）

| 操作 | 命令示例 |
|------|----------|
| 离线批量生成 7 日窗口 summary | `python scripts/experimental/run_history_maintainer_batch.py --db memory.db --symbol NVDA --start 2025-01-01 --end 2025-03-01 --sleep-ms 500` |
| 维护 `analyst_summaries` | 使用 `run_db_viewer` 或 SQLite 客户端按需删改（原 `cleanup_summaries.py` 已移除） |

---

## 其他实验脚本

| 操作 | 命令示例 |
|------|----------|
| 周期反思（周/月） | `python scripts/runtime/run_reflector_cycle.py --cycle weekly --start 2024-01-01 --end 2024-01-07`（根目录 `run_reflector_cycle.py` 亦可） |
| Web 查看 memory.db（含 analyst 报告正文） | `python scripts/experimental/run_db_viewer.py`，浏览器打开 http://127.0.0.1:5555 |
| 去重 analyst_reports | `python scripts/experimental/dedupe_analyst_reports.py --db memory.db` |
| 平台测试 / Graph 辅助 | `scripts/experimental/run_platform_test.py`、`run_analysts_to_db.py`；**从 Summary 跑全图请用** `scripts/runtime/run_signal_export.py`（`--dates` / 区间），`run_graph_from_summary.py` 不再作为主入口 |

---

**最后更新**: 2026-03-24（`run_signal_export`：显式 config 路径、`--dates`、文档对齐 Analyst/LLM/记忆；移除若干实验脚本；LLM 仍为仅 Silicon Flow。）

补充：当前主链路已改为 Trader 直接输出可执行指令（含 `action/target_pct/entry_type/entry_price`），不再依赖 Strategy Selector。
