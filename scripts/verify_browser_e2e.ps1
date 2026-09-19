[CmdletBinding()]
param(
    [int]$Port = 18083
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$TempRoot = [IO.Path]::GetTempPath()
$DocsRoot = Join-Path $TempRoot ("ragforge-browser-e2e-" + [guid]::NewGuid().ToString("N"))
$CodePath = Join-Path $RepoRoot "tests\browser\e2e.js"
$Service = $null
$oldValues = @{}

function Set-TestEnv([string]$Name, [string]$Value) {
    $oldValues[$Name] = [Environment]::GetEnvironmentVariable($Name)
    [Environment]::SetEnvironmentVariable($Name, $Value)
}

function Restore-TestEnv {
    foreach ($name in $oldValues.Keys) {
        [Environment]::SetEnvironmentVariable($name, $oldValues[$name])
    }
}

function Invoke-PlaywrightCli([string[]]$Arguments) {
    & npx.cmd --yes --package @playwright/cli playwright-cli @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Playwright CLI failed with exit code $LASTEXITCODE" }
}

try {
    if (-not (Test-Path -LiteralPath $Python)) { throw "未找到项目虚拟环境：$Python" }
    New-Item -ItemType Directory -Path $DocsRoot -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $DocsRoot "acceptance.md") -Encoding UTF8 -Value @"
# RAG browser acceptance

RAG combines retrieval with generation. The default chunk size is 2200 characters.
"@

    Set-TestEnv "RAG_VECTOR_STORE" "in_memory"
    Set-TestEnv "RAG_EMBEDDER_BACKEND" "deterministic"
    Set-TestEnv "RAG_EMBEDDER_DIM" "64"
    Set-TestEnv "RAG_GENERATION_BACKEND" "offline"
    Set-TestEnv "RAG_DEFAULT_GENERATION_MODEL" "offline"
    Set-TestEnv "RAG_ALLOWED_GENERATION_MODELS" '["offline"]'
    Set-TestEnv "RAG_INGEST_ROOT" $DocsRoot
    Set-TestEnv "RAG_API_KEY" ""
    Set-TestEnv "RAG_ALLOWED_HOSTS" '["127.0.0.1","localhost"]'

    $sourcePath = Join-Path $RepoRoot "src"
    $oldPythonPath = [Environment]::GetEnvironmentVariable("PYTHONPATH")
    try {
        $childPythonPath = if ([string]::IsNullOrWhiteSpace($oldPythonPath)) {
            $sourcePath
        } else {
            "$sourcePath;$oldPythonPath"
        }
        [Environment]::SetEnvironmentVariable("PYTHONPATH", $childPythonPath)
        $Service = Start-Process -FilePath $Python `
            -ArgumentList @("-m", "uvicorn", "ragforge.api.main:app", "--host", "127.0.0.1", "--port", $Port, "--workers", "1") `
            -WorkingDirectory $RepoRoot -WindowStyle Hidden -PassThru
    } finally {
        [Environment]::SetEnvironmentVariable("PYTHONPATH", $oldPythonPath)
    }
    $ready = $false
    $deadline = (Get-Date).AddSeconds(20)
    while ((Get-Date) -lt $deadline) {
        if ($Service.HasExited) { throw "browser E2E API process exited early" }
        try {
            $null = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port/" -TimeoutSec 2
            $ready = $true
            break
        } catch { Start-Sleep -Milliseconds 250 }
    }
    if (-not $ready) { throw "browser E2E API did not become ready" }

    $body = @{ paths = @("acceptance.md") } | ConvertTo-Json -Compress
    $ingest = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:$Port/ingest" `
        -ContentType "application/json" -Body $body -TimeoutSec 20
    if ([int]$ingest.indexed_chunks -le 0) { throw "browser E2E ingest produced no chunks" }

    Invoke-PlaywrightCli @("open", "http://127.0.0.1:$Port/")
    Invoke-PlaywrightCli @("run-code", "--filename", $CodePath)
    Write-Host "PASS: browser core path, export, clear, keyboard and responsive checks."
}
finally {
    Restore-TestEnv
    if ($Service -and -not $Service.HasExited) {
        Stop-Process -Id $Service.Id -Force -ErrorAction SilentlyContinue
        $Service.WaitForExit()
    }
    if (Test-Path -LiteralPath $DocsRoot) {
        Remove-Item -LiteralPath $DocsRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
