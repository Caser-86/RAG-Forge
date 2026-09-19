[CmdletBinding()]
param(
    [ValidateSet("vector-dev", "local", "collector")]
    [string]$Profile = "vector-dev"
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$Locks = @{
    "vector-dev" = "requirements\windows-vector-dev-py314-piptools.txt"
    "local" = "requirements\windows-local-py314-piptools.txt"
    "collector" = "requirements\windows-collector-py314-piptools.txt"
}

if (-not (Test-Path -LiteralPath $Python)) { throw "未找到项目虚拟环境：$Python" }
$LockPath = Join-Path $RepoRoot $Locks[$Profile]
if (-not (Test-Path -LiteralPath $LockPath)) { throw "未找到依赖锁：$LockPath" }

Push-Location $RepoRoot
try {
    & $Python -m pip install -r $LockPath
    if ($LASTEXITCODE -ne 0) { throw "锁文件安装失败：$LockPath" }
    & $Python -m pip install --no-deps .
    if ($LASTEXITCODE -ne 0) { throw "项目 wheel 安装失败" }
    & $Python -m pip check
    if ($LASTEXITCODE -ne 0) { throw "pip check 失败" }
    Write-Host "PASS: Windows $Profile lock installed and pip check passed."
}
finally {
    Pop-Location
}
