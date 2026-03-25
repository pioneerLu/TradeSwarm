# 手动 Lean init：解压浏览器下载的 master.zip，生成 lean.json
# 1. 用浏览器下载 https://github.com/QuantConnect/Lean/archive/refs/heads/master.zip
# 2. 放到项目根目录或通过 -ZipPath 指定
# 3. 在项目根目录运行：.\scripts\setup_lean_manual.ps1

param(
    [string]$ZipPath = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$workspace = Join-Path $root "lean_workspace"
if (-not $ZipPath) { $ZipPath = Join-Path $root "Lean-master.zip" }

if (-not (Test-Path $ZipPath)) {
    Write-Host "请先用浏览器下载 master.zip 并放到: $ZipPath"
    Write-Host "下载地址: https://github.com/QuantConnect/Lean/archive/refs/heads/master.zip"
    exit 1
}

New-Item -ItemType Directory -Force -Path $workspace | Out-Null
$dataDir = Join-Path $workspace "data"
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

Write-Host "解压 $ZipPath ..."
Expand-Archive -Path $ZipPath -DestinationPath (Join-Path $root "Lean-temp") -Force
$extractedData = Join-Path $root "Lean-temp\Lean-master\Data"
if (-not (Test-Path $extractedData)) {
    $extractedData = Join-Path $root "Lean-temp\QuantConnect-Lean-master\Data"
}
if (-not (Test-Path $extractedData)) {
    Write-Host "未找到 Data 目录，请检查 zip 结构"
    exit 1
}
Copy-Item -Path "$extractedData\*" -Destination $dataDir -Recurse -Force
Remove-Item -Path (Join-Path $root "Lean-temp") -Recurse -Force -ErrorAction SilentlyContinue

$storageDir = Join-Path $workspace "storage"
New-Item -ItemType Directory -Force -Path $storageDir | Out-Null

$leanJson = @'
{
  "data-folder": "data",
  "environment": "backtesting",
  "log-handler": "QuantConnect.Logging.CompositeLogHandler",
  "messaging-handler": "QuantConnect.Messaging.Messaging",
  "job-queue-handler": "QuantConnect.Queues.JobQueue",
  "api-handler": "QuantConnect.Api.Api",
  "map-file-provider": "QuantConnect.Data.Auxiliary.LocalDiskMapFileProvider",
  "factor-file-provider": "QuantConnect.Data.Auxiliary.LocalDiskFactorFileProvider",
  "data-provider": "QuantConnect.Lean.Engine.DataFeeds.DefaultDataProvider",
  "data-channel-provider": "DataChannelProvider",
  "object-store": "QuantConnect.Lean.Engine.Storage.LocalObjectStore",
  "data-aggregator": "QuantConnect.Lean.Engine.DataFeeds.AggregationManager",
  "symbol-minute-limit": 10000,
  "symbol-second-limit": 10000,
  "symbol-tick-limit": 10000,
  "maximum-data-points-per-chart-series": 4000,
  "force-exchange-always-open": false,
  "transaction-log": "",
  "environments": {
    "backtesting": {
      "live-mode": false,
      "setup-handler": "QuantConnect.Lean.Engine.Setup.ConsoleSetupHandler",
      "result-handler": "QuantConnect.Lean.Engine.Results.BacktestingResultHandler",
      "data-feed-handler": "QuantConnect.Lean.Engine.DataFeeds.FileSystemDataFeed",
      "real-time-handler": "QuantConnect.Lean.Engine.RealTime.BacktestingRealTimeHandler",
      "history-provider": "QuantConnect.Lean.Engine.HistoricalData.SubscriptionDataReaderHistoryProvider",
      "transaction-handler": "QuantConnect.Lean.Engine.TransactionHandlers.BacktestingTransactionHandler"
    }
  }
}
'@
$leanJsonPath = Join-Path $workspace "lean.json"
$leanJson | Out-File -FilePath $leanJsonPath -Encoding utf8

Write-Host "已创建 lean.json 和 data/。后续："
Write-Host "  cd lean_workspace"
Write-Host "  ..\scripts\run_lean_no_proxy.ps1 project-create TradeSwarm --language python"
Write-Host "  (复制 main.py 和 signals.json 后)"
Write-Host "  ..\scripts\run_lean_no_proxy.ps1 backtest TradeSwarm --download-data"
