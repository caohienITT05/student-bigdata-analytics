$ErrorActionPreference = 'Stop'
$appRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
Push-Location -LiteralPath $appRoot
try {
    & (Join-Path $appRoot '.venv/Scripts/python.exe') -m uvicorn main:app --host 127.0.0.1 --port 8000
} finally { Pop-Location }
