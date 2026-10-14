$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$appPath = Join-Path $scriptDir "app.py"
$venvPython = Join-Path $scriptDir ".venv\Scripts\python.exe"

if (Test-Path -LiteralPath $venvPython) {
    & $venvPython $appPath --open @args
    exit $LASTEXITCODE
}

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 $appPath --open @args
    exit $LASTEXITCODE
}

if (Get-Command python -ErrorAction SilentlyContinue) {
    & python $appPath --open @args
    exit $LASTEXITCODE
}

Write-Host "未找到 Python。请安装 Python 3.10+，创建 .venv 并安装 requirements.txt 中的依赖。" -ForegroundColor Red
exit 1
