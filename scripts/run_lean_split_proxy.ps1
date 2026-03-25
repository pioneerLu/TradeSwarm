# Lean CLI 分域代理：QuantConnect 直连，其余走代理
# 用法：.\scripts\run_lean_split_proxy.ps1 init

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$workspace = Join-Path $root "lean_workspace"
if (-not (Test-Path $workspace)) { Write-Error "lean_workspace 不存在: $workspace" }

$env:NO_PROXY = "quantconnect.com,www.quantconnect.com,cdn.quantconnect.com,api.quantconnect.com"

Push-Location $workspace
try {
    Write-Host "[run_lean_split_proxy] NO_PROXY=QuantConnect，执行 lean $args"
    & lean @args
} finally {
    Pop-Location
}
