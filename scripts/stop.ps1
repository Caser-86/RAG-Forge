[CmdletBinding()]
param([int]$TimeoutSeconds = 15)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$StatePath = Join-Path $RepoRoot "data\run\ragforge.pid.json"

function Get-CommandLine([int]$ProcessId) {
    $record = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction SilentlyContinue
    if ($record) { return [string]$record.CommandLine }
    return ""
}

function Test-OwnedProcess($State) {
    if (-not $State -or -not $State.pid) { return $false }
    $process = Get-Process -Id ([int]$State.pid) -ErrorAction SilentlyContinue
    if (-not $process) { return $false }
    if ($process.Path -and -not [String]::Equals($process.Path, [string]$State.executable, [StringComparison]::OrdinalIgnoreCase)) { return $false }
    $commandLine = Get-CommandLine ([int]$State.pid)
    if (-not ($commandLine -like "*$($State.project_path)*")) { return $false }
    if (-not ($commandLine -match "uvicorn")) { return $false }
    try {
        $actualStart = $process.StartTime.ToUniversalTime()
        $recordedStart = if ($State.process_start_time -is [DateTime]) {
            $State.process_start_time.ToUniversalTime()
        } else {
            [DateTimeOffset]::Parse([string]$State.process_start_time).UtcDateTime
        }
        if ([Math]::Abs(($actualStart - $recordedStart).TotalSeconds) -gt 5) { return $false }
    } catch { return $false }
    return $true
}

if (-not (Test-Path -LiteralPath $StatePath)) { Write-Host "RAG-Forge 未运行（无自有状态文件）"; exit 0 }
try { $state = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json }
catch { throw "运行状态文件损坏，已停止操作：$StatePath" }
if (-not (Test-OwnedProcess $state)) { throw "未能确认 PID $($state.pid) 属于本项目，未停止任何进程" }

$ownedPid = [int]$state.pid
Stop-Process -Id $ownedPid
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
while ((Get-Date) -lt $deadline) {
    if (-not (Get-Process -Id $ownedPid -ErrorAction SilentlyContinue)) { break }
    Start-Sleep -Milliseconds 250
}
if (Get-Process -Id $ownedPid -ErrorAction SilentlyContinue) {
    if (-not (Test-OwnedProcess $state)) { throw "进程身份在强制停止前发生变化，已中止" }
    Stop-Process -Id $ownedPid -Force
}
if (Get-Process -Id $ownedPid -ErrorAction SilentlyContinue) { throw "无法停止自有 RAG-Forge 进程 PID $ownedPid" }
Remove-Item -LiteralPath $StatePath -Force
Write-Host "RAG-Forge 已停止：PID $ownedPid。未停止用户 Ollama 或其他进程。"
