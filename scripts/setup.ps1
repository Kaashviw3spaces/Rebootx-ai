# ==============================================================================
# REBOOTX — Windows PowerShell Setup Wrapper
# ==============================================================================
param(
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $projectRoot

# Locate Python executable
$pythonExe = $null
if (Test-Path -LiteralPath (Join-Path $projectRoot 'backend\.venv\Scripts\python.exe')) {
    $pythonExe = Join-Path $projectRoot 'backend\.venv\Scripts\python.exe'
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonExe = 'python'
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonExe = 'py'
} else {
    Write-Error "Python 3.10+ is required but was not found in PATH or backend/.venv."
    exit 1
}

$scriptArgs = @('scripts/setup.py')
if ($Force) {
    $scriptArgs += '--force'
}

& $pythonExe $scriptArgs

