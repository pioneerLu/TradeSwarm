# QuantConnect 回测项目（方案 A）

TradeSwarm Agent 输出信号，QuantConnect 平台执行回测。**仅使用平台数据，无回退、无模拟**。

## 网页版 vs 本地自动化

| 方式 | 适用场景 | 自动化 |
|------|----------|--------|
| **Algorithm Lab（云上）** | 偶发验证、无本地环境 | 需每次手动粘贴 EMBEDDED_SIGNALS |
| **Lean CLI + `scripts/runtime/run_automated_backtest.py`** | 每日回测、长期测试、CI | 一键或定时任务全自动 |

**每日回测建议**：使用 `scripts/runtime/run_automated_backtest.py`（或仓库根目录同名薄封装），可定时执行，无需复制到网页。

## 前置步骤

1. **Lean CLI**：`pip install lean`，`lean login`
2. **Docker**：本地回测需 Docker
3. **Lean 初始化**：按 [docs/LEAN_LOCAL_SETUP.md](../docs/LEAN_LOCAL_SETUP.md) 完成

## 运行回测

### 方式一：自动化脚本（推荐，适合每日/定时）

```bash
# 从仓库根执行；根目录 run_automated_backtest.py 为薄封装，等价于下方路径
# 从 analyst_reports 导出信号并执行 lean 回测（一键完成）
python scripts/runtime/run_automated_backtest.py --source export --start 2025-01-01 --end 2025-03-01

# 仅导出+复制，不执行回测
python scripts/runtime/run_automated_backtest.py --source export --skip-backtest

# 从 daily_results 转换并回测
python scripts/runtime/run_automated_backtest.py --source daily --daily-dir backtest_results/daily_results
```

脚本会自动：导出信号 → 复制到 Lean 项目 → 执行 lean backtest → 保存摘要到 `backtest_summaries/`。可配合 Windows 任务计划或 cron 做每日回测。

### 方式二：云上（QuantConnect Algorithm Lab）

1. 登录 https://www.quantconnect.com/terminal/
2. 新建 Python 算法，粘贴 `quantconnect/main.py` 内容
3. **手动**将 `qc_signals/signals.json` 的 `by_execution_date` 粘贴到 `EMBEDDED_SIGNALS`
4. 确认 `set_start_date` / `set_end_date` 与信号日期一致
5. 运行回测

不适合频繁更新场景（每次需重新粘贴）。

### 方式三：本地 Lean CLI 手动

```powershell
# 先导出信号
python scripts/runtime/run_signal_export.py --symbol NVDA --start 2025-01-01 --end 2025-03-01 --output qc_signals

# 复制并回测（或直接用 scripts/runtime/run_automated_backtest.py）
.\scripts\run_lean_no_proxy.ps1 backtest TradeSwarm --download-data
```

信号文件置于 `quantconnect/signals/` 或 `lean_workspace/TradeSwarm/signals/`，算法会自动读取。

## 信号格式

`signals.json` 示例：

```json
{
  "symbol": "NVDA",
  "start_date": "2025-01-01",
  "end_date": "2025-03-01",
  "by_execution_date": {
    "2025-01-15": { "action": "BUY", "target_pct": 0.1, ... },
    "2025-02-20": { "action": "SELL", "target_pct": 0, ... }
  }
}
```

算法在每日开盘后按 `execution_date` 查找信号并执行 `SetHoldings` 或 `Liquidate`。
