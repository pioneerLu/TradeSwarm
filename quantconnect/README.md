# QuantConnect 回测（TradeSwarm）

TradeSwarm 负责生成 `signals.json`，QuantConnect/Lean 负责执行回测。  
当前仓库支持两条数据路径：

- **路径 A（本地数据）**：`yfinance`（失败时回退 `stooq`）下载行情，写入 Lean custom data，再本地 Docker 回测。
- **路径 B（平台数据）**：Lean `--download-data` 下载 QuantConnect 数据（需要对应数据权限）。

## 前置条件

1. Lean CLI：`pip install lean`，并完成 `lean login`
2. Docker Desktop 已启动
3. Lean 本地工程已初始化（见 [docs/LEAN_LOCAL_SETUP.md](../docs/LEAN_LOCAL_SETUP.md)）
4. 建议在 `langchain` 环境执行 Python 脚本

## 路径 A：使用 yfinance/stooq 本地数据回测（推荐）

### 1) 下载并生成 Lean custom CSV

```powershell
conda run -n langchain python scripts/runtime/download_yf_for_lean.py --symbol NVDA --start 2025-01-01 --end 2025-03-01 --output lean_workspace/data/custom/nvda_daily.csv
```

输出文件格式为：

```text
date,open,high,low,close,volume
```

### 2) 导出交易信号

```powershell
conda run -n langchain python scripts/runtime/run_signal_export.py --symbol NVDA --start 2025-01-01 --end 2025-03-01 --db memory.db --output qc_signals
```

### 3) 回测（使用本地 custom 数据）

`quantconnect/main.py` 已优先加载 `custom/nvda_daily.csv`。  
若 `TS_LOCAL_DATA` 未显式设为 `0`，默认走本地数据路径。

```powershell
.\scripts\run_lean_no_proxy.ps1 backtest TradeSwarm --download-data
```

> 说明：即便带 `--download-data`，算法本身仍优先使用 custom 数据；该参数主要用于 Lean 常规流程兼容。

## 路径 B：使用 QuantConnect 平台数据

当你有对应数据权限（如 US Equity Security Master）时，可直接让算法回退到 `add_equity`。

```powershell
$env:TS_LOCAL_DATA="0"
.\scripts\run_lean_no_proxy.ps1 backtest TradeSwarm --download-data
Remove-Item Env:TS_LOCAL_DATA
```

## 自动化回测（每日/定时）

可使用 `run_automated_backtest.py` 做一键导出+复制+回测：

```powershell
conda run -n langchain python scripts/runtime/run_automated_backtest.py --source export --start 2025-01-01 --end 2025-03-01
```

该脚本会自动：

1. 导出 `qc_signals/signals.json`
2. 复制到 `quantconnect/signals/` 和 `lean_workspace/TradeSwarm/signals/`
3. 同步 `quantconnect/main.py` 到 Lean 工作区
4. 执行回测并生成 `backtest_summaries/*.json`

## 云端 Algorithm Lab（无需本地 Docker）

若只想在网页云端跑回测，可把信号嵌入单文件算法：

```powershell
conda run -n langchain python scripts/runtime/build_qc_embedded_main.py
```

然后将生成的 `lean_workspace/TradeSwarm/main.py` 全量粘贴到 QuantConnect Algorithm Lab 运行。

## 信号格式

`signals.json` 使用 `by_execution_date`：

```json
{
  "symbol": "NVDA",
  "start_date": "2025-01-01",
  "end_date": "2025-03-01",
  "by_execution_date": {
    "2025-01-03": {
      "action": "BUY",
      "target_pct": 0.5,
      "entry_type": "MKT_OPEN"
    }
  }
}
```

算法在 `on_data` 中按交易日读取当天信号，执行 `set_holdings` / `liquidate` / 条件单。
