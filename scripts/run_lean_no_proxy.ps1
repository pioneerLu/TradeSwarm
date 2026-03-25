# Lean CLI 代理隔离：清除代理后执行 lean
# 用法：在项目根目录运行 .\scripts\run_lean_no_proxy.ps1 init
#       .\scripts\run_lean_no_proxy.ps1 backtest TradeSwarm --download-data

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$workspace = Join-Path $root "lean_workspace"
if (-not (Test-Path $workspace)) {
    Write-Error "lean_workspace 不存在: $workspace"
}

$env:HTTP_PROXY = ""
$env:HTTPS_PROXY = ""
$env:http_proxy = ""
$env:https_proxy = ""
$env:ALL_PROXY = ""
$env:all_proxy = ""
$env:NO_PROXY = "quantconnect.com,www.quantconnect.com,cdn.quantconnect.com,api.quantconnect.com,github.com,raw.githubusercontent.com"

Push-Location $workspace
try {
    Write-Host "[run_lean_no_proxy] 已清除代理，在 $workspace 执行 lean $args"
    & lean @args
} finally {
    Pop-Location
}
