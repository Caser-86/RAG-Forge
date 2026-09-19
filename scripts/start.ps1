[CmdletBinding()]
param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8000,
    [int]$ReadinessTimeoutSeconds = 60
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$RunDir = Join-Path $RepoRoot "data\run"
$StatePath = Join-Path $RunDir "ragforge.pid.json"
$StdoutPath = Join-Path $RunDir "ragforge.stdout.log"
$StderrPath = Join-Path $RunDir "ragforge.stderr.log"

function Read-State {
    if (-not (Test-Path -LiteralPath $StatePath)) { return $null }
    try { return Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json }
    catch { throw "运行状态文件损坏：$StatePath" }
}

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

function Get-OllamaModels([string]$BaseUrl) {
    try {
        $response = Invoke-RestMethod -Uri "$($BaseUrl.TrimEnd('/'))/api/tags" -TimeoutSec 5
        return @($response.models | ForEach-Object { [string]$_.name })
    } catch {
        return @()
    }
}

function Assert-ModelReadiness {
    $backend = Get-DotEnvValue "RAG_EMBEDDER_BACKEND" "ollama"
    $generationBackend = Get-DotEnvValue "RAG_GENERATION_BACKEND" "ollama"
    if ($backend -ne "ollama" -and $generationBackend -ne "ollama") {
        Write-Host "Ollama: skipped（当前后端不依赖 Ollama）"
        return
    }
    $ollamaUrl = Get-DotEnvValue "RAG_OLLAMA_BASE_URL" "http://127.0.0.1:11434"
    $models = Get-OllamaModels $ollamaUrl
    if ($models.Count -eq 0) { throw "Ollama 不可用或未返回模型：$ollamaUrl" }
    $embedderModel = Get-DotEnvValue "RAG_EMBEDDER_MODEL" "bge-m3"
    $generationModel = Get-DotEnvValue "RAG_DEFAULT_GENERATION_MODEL" "gemma3:4b"
    $hasEmbedder = $models -contains $embedderModel -or ($embedderModel -eq "bge-m3" -and $models -contains "bge-m3:latest")
    $hasGeneration = $models -contains $generationModel
    if ($backend -eq "ollama" -and -not $hasEmbedder) { throw "缺少必需嵌入模型：$embedderModel" }
    if ($generationBackend -eq "ollama" -and -not $hasGeneration) { throw "缺少必需生成模型：$generationModel" }
    $optional = @("gemma4:e4b", "qwen3:0.6b") | Where-Object { $models -notcontains $_ }
    if ($optional.Count -gt 0) { Write-Warning ("可选模型未安装：" + ($optional -join ", ") + "；基础服务仍可启动") }
    Write-Host ("Ollama: READY；已发现 " + $models.Count + " 个模型")
}

function Show-RuntimeProfile {
    $vectorStore = Get-DotEnvValue "RAG_VECTOR_STORE" "qdrant_local"
    $embedderBackend = Get-DotEnvValue "RAG_EMBEDDER_BACKEND" "ollama"
    $generationBackend = Get-DotEnvValue "RAG_GENERATION_BACKEND" "ollama"
    $collection = Get-DotEnvValue "RAG_QDRANT_COLLECTION" "rag_forge_local_v1"
    $manifest = Get-DotEnvValue "RAG_INDEX_MANIFEST_PATH" "data/index_manifest.json"
    Write-Host "Profile: vector_store=$vectorStore; embedder=$embedderBackend; generation=$generationBackend"
    Write-Host "Index: collection=$collection; manifest=$manifest"
    if ($vectorStore -eq "in_memory") {
        Write-Warning "当前是 in_memory 临时 profile；重启后索引会丢失，不适合作为本地发布环境"
    }
    $manifestPath = if ([IO.Path]::IsPathRooted($manifest)) { $manifest } else { Join-Path $RepoRoot $manifest }
    if ($vectorStore -ne "in_memory" -and -not (Test-Path -LiteralPath $manifestPath)) {
        Write-Warning "未发现 index manifest；空库可以启动，已有持久化集合必须先执行 reindex"
    }
}

function Assert-BindSecurity {
    $normalizedHost = $HostAddress.Trim().ToLowerInvariant()
    $isLoopback = $normalizedHost -in @("127.0.0.1", "localhost", "::1", "[::1]")
    $apiKey = Get-DotEnvValue "RAG_API_KEY" ""
    if (-not $isLoopback -and [string]::IsNullOrWhiteSpace($apiKey)) {
        throw "非 loopback 地址启动必须配置 RAG_API_KEY；当前 HostAddress=$HostAddress"
    }
}

if (-not (Test-Path -LiteralPath $Python)) { throw "未找到项目虚拟环境：$Python" }
New-Item -ItemType Directory -Path $RunDir -Force | Out-Null

$state = Read-State
if (Test-OwnedProcess $state) {
    Write-Host "RAG-Forge 已在运行：http://$HostAddress`:$($state.port)（PID $($state.pid)）"
    exit 0
}

$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($listener) { throw "端口 $Port 已被其他进程占用，未停止或覆盖该进程" }
Assert-BindSecurity
Show-RuntimeProfile
Assert-ModelReadiness

$sourcePath = Join-Path $RepoRoot "src"
$oldPythonPath = [Environment]::GetEnvironmentVariable("PYTHONPATH")
try {
    $env:PYTHONPATH = if ([string]::IsNullOrWhiteSpace($oldPythonPath)) {
        $sourcePath
    } else {
        "$sourcePath;$oldPythonPath"
    }
    $process = Start-Process -FilePath $Python `
        -ArgumentList @("-m", "uvicorn", "ragforge.api.main:app", "--host", $HostAddress, "--port", $Port, "--workers", "1") `
        -WorkingDirectory $RepoRoot -WindowStyle Hidden `
        -RedirectStandardOutput $StdoutPath -RedirectStandardError $StderrPath -PassThru
} finally {
    if ($null -eq $oldPythonPath) {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    } else {
        $env:PYTHONPATH = $oldPythonPath
    }
}
$state = [ordered]@{
    schema_version = 1
    pid = $process.Id
    project_path = $RepoRoot
    executable = $Python
    host = $HostAddress
    port = $Port
    started_at = [DateTimeOffset]::UtcNow.ToString("o")
    process_start_time = $process.StartTime.ToUniversalTime().ToString("o")
    stdout_log = $StdoutPath
    stderr_log = $StderrPath
}
$state | ConvertTo-Json | Set-Content -LiteralPath $StatePath -Encoding UTF8

$deadline = (Get-Date).AddSeconds($ReadinessTimeoutSeconds)
$ready = $false
while ((Get-Date) -lt $deadline) {
    if ($process.HasExited) { break }
    try {
        $null = Invoke-WebRequest -UseBasicParsing -Uri "http://$HostAddress`:$Port/" -TimeoutSec 2
        $ready = $true
        break
    } catch { Start-Sleep -Milliseconds 500 }
}
if (-not $ready) {
    if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force }
    Remove-Item -LiteralPath $StatePath -Force -ErrorAction SilentlyContinue
    $tail = if (Test-Path -LiteralPath $StderrPath) { (Get-Content -LiteralPath $StderrPath -Tail 20) -join "`n" } else { "" }
    throw "服务在 ${ReadinessTimeoutSeconds}s 内未就绪。stderr：$tail"
}
Write-Host "RAG-Forge READY：http://$HostAddress`:$Port"
Write-Host "状态：$StatePath"
Write-Host "日志：$StdoutPath / $StderrPath"
