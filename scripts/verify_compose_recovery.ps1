[CmdletBinding()]
param(
    [switch]$RunRecreate,
    [switch]$UseOllama,
    [int]$ApiPort = 18081,
    [int]$QdrantPort = 16333
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot ".." -ChildPath "")).Path
$projectName = "ragforge-acceptance-$([guid]::NewGuid().ToString('N').Substring(0, 10))"
$composeArgs = @(
    "--project-name", $projectName,
    "--file", (Join-Path $root "docker-compose.yml")
)
if ($UseOllama) {
    $composeArgs += @("--file", (Join-Path $root "docker-compose.ollama.yml"))
}

Push-Location $root
$tempRoot = $null
$oldDocsDir = $env:RAGFORGE_DOCS_DIR
$oldApiPort = $env:RAGFORGE_API_HOST_PORT
$oldQdrantPort = $env:RAGFORGE_QDRANT_HOST_PORT
try {
    Write-Host "Validating isolated Compose configuration..."
    & docker compose @composeArgs config --quiet
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose config failed"
    }

    if (-not $RunRecreate) {
        Write-Host "Compose config is valid. Pass -RunRecreate to run the isolated recreate check."
        return
    }

    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) "ragforge-compose-$([guid]::NewGuid().ToString('N'))"
    New-Item -ItemType Directory -Path $tempRoot | Out-Null
    $documentPath = Join-Path $tempRoot "acceptance.md"
    Set-Content -LiteralPath $documentPath -Value "# Compose recovery`n`nThis document verifies API state survives recreate." -Encoding utf8
    $env:RAGFORGE_DOCS_DIR = $tempRoot
    $env:RAGFORGE_API_HOST_PORT = [string]$ApiPort
    $env:RAGFORGE_QDRANT_HOST_PORT = [string]$QdrantPort

    Write-Host "Starting isolated project $projectName ..."
    & docker compose @composeArgs up -d --force-recreate qdrant api
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose up failed"
    }

    $uri = "http://127.0.0.1:$ApiPort/api/health"
    $health = $null
    for ($attempt = 1; $attempt -le 45; $attempt++) {
        try {
            $health = Invoke-RestMethod -Uri $uri -TimeoutSec 3
            break
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    if ($null -eq $health) {
        throw "API did not become healthy within 90 seconds"
    }

    $ingestBody = @{ paths = @("acceptance.md") } | ConvertTo-Json -Compress
    try {
        $before = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:$ApiPort/ingest" `
            -ContentType "application/json" -Body $ingestBody -TimeoutSec 30
    } catch {
        throw "isolated API ingest failed; ensure the configured API key/model cache is available"
    }
    if ([int]$before.indexed_chunks -le 0) {
        throw "isolated API ingest produced no chunks"
    }

    Write-Host "Recreating API container only..."
    & docker compose @composeArgs up -d --force-recreate api
    if ($LASTEXITCODE -ne 0) {
        throw "API recreate failed"
    }

    $after = $null
    for ($attempt = 1; $attempt -le 45; $attempt++) {
        try {
            $after = Invoke-RestMethod -Uri $uri -TimeoutSec 3
            if ([int]$after.indexed_chunks -gt 0) { break }
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    if ($null -eq $after -or [int]$after.indexed_chunks -ne [int]$before.indexed_chunks) {
        throw "indexed chunk count changed across API recreate"
    }
    Write-Host "PASS: API recreate preserved indexed chunk count and persistent state."
}
finally {
    if ($RunRecreate) {
        & docker compose @composeArgs down --remove-orphans | Out-Null
    }
    if ($null -ne $tempRoot -and (Test-Path -LiteralPath $tempRoot)) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
    if ($null -eq $oldDocsDir) { Remove-Item Env:RAGFORGE_DOCS_DIR -ErrorAction SilentlyContinue } else { $env:RAGFORGE_DOCS_DIR = $oldDocsDir }
    if ($null -eq $oldApiPort) { Remove-Item Env:RAGFORGE_API_HOST_PORT -ErrorAction SilentlyContinue } else { $env:RAGFORGE_API_HOST_PORT = $oldApiPort }
    if ($null -eq $oldQdrantPort) { Remove-Item Env:RAGFORGE_QDRANT_HOST_PORT -ErrorAction SilentlyContinue } else { $env:RAGFORGE_QDRANT_HOST_PORT = $oldQdrantPort }
    Pop-Location
}
