[CmdletBinding()]
param([switch]$Json)

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

function Get-DotEnvValue([string]$Name, [string]$Fallback = "") {
    $environmentValue = [Environment]::GetEnvironmentVariable($Name)
    if ($null -ne $environmentValue) { return $environmentValue }
    $envPath = Join-Path $RepoRoot ".env"
    if (-not (Test-Path -LiteralPath $envPath)) { return $Fallback }
    foreach ($line in Get-Content -LiteralPath $envPath) {
        if ($line -match "^\s*$Name\s*=\s*(.*)\s*$") {
            return $Matches[1].Trim().Trim('"').Trim("'")
        }
    }
    return $Fallback
}

$result = [ordered]@{ status = "NOT_RUNNING"; state_file = $StatePath; pid = $null; url = $null; health = $null; error = $null }
if (-not (Test-Path -LiteralPath $StatePath)) {
    if ($Json) { $result | ConvertTo-Json -Depth 5 } else { Write-Host "RAG-Forge: NOT_RUNNING" }
    exit 0
}
try { $state = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json }
catch { $result.status = "INVALID_STATE"; $result.error = "运行状态文件损坏"; if ($Json) { $result | ConvertTo-Json -Depth 5 } else { Write-Host "RAG-Forge: INVALID_STATE" }; exit 1 }

$result.pid = [int]$state.pid
$result.url = "http://$($state.host):$($state.port)"
if (-not (Test-OwnedProcess $state)) {
    $result.status = "STALE_OR_NOT_OWNED"
    $result.error = "PID、启动时间或项目命令行无法证明属于 RAG-Forge；未执行任何停止操作"
    if ($Json) { $result | ConvertTo-Json -Depth 5 } else { Write-Host "RAG-Forge: $($result.status) (PID $($result.pid))"; Write-Host $result.error }
    exit 1
}
try {
    $headers = @{}
    $apiKey = Get-DotEnvValue "RAG_API_KEY" ""
    if ($apiKey) { $headers["X-API-Key"] = $apiKey }
    $result.health = Invoke-RestMethod -Uri "$($result.url)/api/health" -Headers $headers -TimeoutSec 5
    $result.status = "READY"
} catch {
    $result.status = "PROCESS_RUNNING_NOT_READY"
    $result.error = $_.Exception.Message
}
if ($Json) { $result | ConvertTo-Json -Depth 8 }
else {
    Write-Host "RAG-Forge: $($result.status)"
    Write-Host "URL: $($result.url)  PID: $($result.pid)"
    if ($result.health) { Write-Host ("indexed_chunks: " + $result.health.indexed_chunks + "; reranker_available: " + $result.health.reranker_available) }
    if ($result.error) { Write-Host "错误: $($result.error)" }
}
if ($result.status -eq "READY") { exit 0 } else { exit 1 }
