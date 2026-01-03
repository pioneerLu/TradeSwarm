# 交易系统时序与调度设计 (Timing & Scheduling)

本系统采用 **"慢思考 (LLM) + 快执行 (Algo)"** 的混合架构，严格按照交易日的时间轴进行调度。

## 1. 每日时间轴概览

| 时间窗口 | 阶段名称 | 核心组件 | 任务描述 | 状态标记 |
| :--- | :--- | :--- | :--- | :--- |
| **09:00 - 09:25** | **盘前战略 (Pre-Market)** | Fusion Node (LLM) | 分析历史/新闻，制定 `ExecutionPlan` | `pre_market` |
| **09:30 - 11:30**<br>**13:00 - 15:00** | **盘中执行 (Intraday)** | Algo Loop (Python) | 监控行情，执行计划，生成 `ExecutionLog` | `intraday` |
| **15:00 - 15:30** | **盘后复盘 (Post-Market)** | Fusion Node (LLM) | 复盘执行结果，更新 Memory，调整策略 | `post_market` |
| **15:30 - 09:00** | **休眠 (Sleep)** | System | 等待下一个交易日 | `sleep` |

---

## 2. 详细调度逻辑

### 2.1 盘前阶段 (Pre-Market)
*   **触发条件**: 系统时间到达 09:00。
*   **输入**: 
    *   截止昨日的日线数据 (Daily OHLCV)。
    *   隔夜新闻与宏观数据。
    *   `FinancialSituationMemory` (长期记忆)。
*   **流程**:
    1.  **Research Subgraph**: 分析师团队评估市场环境，提出初步策略。
    2.  **Risk Subgraph**: 风控团队审核策略，设定硬性约束（止损位、仓位上限）。
    3.  **Fusion Node**: 综合意见，生成结构化的 `ExecutionPlan`。
*   **输出**: `FusionState.execution_plan` 被填充。

### 2.2 盘中阶段 (Intraday)
*   **触发条件**: 系统时间进入交易时段，且 `execution_plan` 已就绪。
*   **机制**: **死循环 (While Loop) 或 定时任务 (Cron)**，严禁调用 LLM。
*   **流程**:
    1.  **Fetch**: 每分钟获取最新 K 线 (1min Bar) 和快照 (Snapshot)。
    2.  **Check**: 
        *   检查 `plan.validity_factors` (如 RSI < 70)。
        *   检查 `plan.parameters.trigger_condition` (如 Price > MA20)。
        *   检查止损/止盈条件。
    3.  **Execute**: 调用交易接口下单。
    4.  **Log**: 记录操作到 `ExecutionLog`。
*   **输出**: `FusionState.execution_log` 被填充。

### 2.3 盘后阶段 (Post-Market)
*   **触发条件**: 系统时间到达 15:00 收盘。
*   **输入**:
    *   `FusionState.execution_log` (今日战况)。
    *   今日日线收盘数据。
*   **流程**:
    1.  **Data Archival**: 将今日日线存入数据库/文件。
    2.  **Review**: LLM 分析 `ExecutionLog`。
        *   *Did we win?* (盈利分析)
        *   *Did the strategy work?* (策略有效性验证)
    3.  **Memory Update**: 更新 `FinancialSituationMemory`，标记当前策略状态（有效/失效/需观察）。
*   **输出**: 更新后的 Memory，以及对明日的初步建议。

---

## 3. 异常处理与人工干预

*   **紧急停止**: 提供 `Emergency Stop` 按钮，强制中断 Intraday Loop 并清仓/锁仓。
*   **策略失效**: 若盘中亏损超过阈值（如 -5%），Algo 自动停止交易并发送警报，不再等待盘后复盘。
*   **数据缺失**: 若盘前无法获取数据，跳过当日交易，直接进入 Sleep 状态。
