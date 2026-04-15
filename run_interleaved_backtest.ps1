# TradeSwarm - Agent-QC Interleaved Backtest (one-click)
# Usage: right-click -> "Run with PowerShell" or execute in terminal
#
# Configurable parameters (edit below):
$Symbol       = "NVDA"
$StartDate    = "2025-01-02"
$EndDate      = "2025-01-10"
$InitialCash  = 100000
$DbPath       = "storage\db\memory.db"
$Analysts     = "market,news,sentiment,fundamentals"
# Set to 1 for fast smoke test, $null for full debate rounds
$MaxResearchRounds = 1
$MaxRiskRounds     = 1

# ─── No edits needed below this line ───────────────────────────
$ErrorActionPreference = "Stop"
$root = Split-Path $MyInvocation.MyCommand.Path -Parent

# Clear proxy (Lean/Docker requirement)
$env:HTTP_PROXY  = ""
$env:HTTPS_PROXY = ""
$env:http_proxy  = ""
$env:https_proxy = ""
$env:ALL_PROXY   = ""
$env:all_proxy   = ""
$env:PYTHONUNBUFFERED = "1"

# Activate conda environment
$condaExe = "D:\Software\Anaconda\Scripts\conda.exe"
if (Test-Path $condaExe) {
    & $condaExe activate langchain 2>$null
    $env:PATH = "D:\Software\Anaconda\envs\langchain;D:\Software\Anaconda\envs\langchain\Scripts;" + $env:PATH
}

$pythonExe = "D:\Software\Anaconda\envs\langchain\python.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = "python"
}

$script = Join-Path $root "scripts\runtime\run_interleaved_backtest.py"

$args = @(
    "-u", $script,
    "--symbol", $Symbol,
    "--start", $StartDate,
    "--end", $EndDate,
    "--db", $DbPath,
    "--initial-cash", $InitialCash,
    "--enabled-analysts", $Analysts,
    "-v"
)

if ($MaxResearchRounds -ne $null) {
    $args += @("--max-research-debate-rounds", $MaxResearchRounds)
}
if ($MaxRiskRounds -ne $null) {
    $args += @("--max-risk-debate-rounds", $MaxRiskRounds)
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "TradeSwarm Interleaved Backtest" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Symbol: $Symbol  Range: $StartDate ~ $EndDate"
Write-Host "Cash: `$$InitialCash  Analysts: $Analysts"
Write-Host "Research rounds: $MaxResearchRounds  Risk rounds: $MaxRiskRounds"
Write-Host ""

Push-Location $root
try {
    & $pythonExe @args
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "Done. Press any key to exit..." -ForegroundColor Green
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
