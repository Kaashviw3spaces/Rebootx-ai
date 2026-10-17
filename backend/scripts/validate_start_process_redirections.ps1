# backend/scripts/validate_start_process_redirections.ps1
$ErrorActionPreference = 'Stop'
$file = (Resolve-Path 'backend/scripts/run_cp6_live_recovery.ps1').Path
$content = Get-Content -LiteralPath $file -Raw

$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($file, [ref]$tokens, [ref]$errors)

if ($errors.Count -gt 0) {
    Write-Error "PowerShell AST syntax errors found ($($errors.Count))"
    exit 1
}

# Find all CommandAst nodes where CommandName is Start-Process
$startProcessCalls = $ast.FindAll({ $args[0] -is [System.Management.Automation.Language.CommandAst] -and $args[0].GetCommandName() -eq 'Start-Process' }, $true)

Write-Host "Found $($startProcessCalls.Count) Start-Process invocations."
if ($startProcessCalls.Count -eq 0) { throw "No Start-Process invocations found!" }

$i = 0
foreach ($call in $startProcessCalls) {
    $i++
    $outParam = $null
    $errParam = $null

    $elements = $call.CommandElements
    for ($idx = 0; $idx -lt $elements.Count; $idx++) {
        $el = $elements[$idx]
        if ($el.Extent.Text -eq '-RedirectStandardOutput') {
            $outParam = $elements[$idx + 1].Extent.Text
        }
        if ($el.Extent.Text -eq '-RedirectStandardError') {
            $errParam = $elements[$idx + 1].Extent.Text
        }
    }

    Write-Host "Invocation $i (Line $($call.Extent.StartLineNumber)):"
    Write-Host "  Stdout: $outParam"
    Write-Host "  Stderr: $errParam"

    if (-not $outParam -or -not $errParam) {
        throw "Invocation $i missing stdout or stderr redirection!"
    }
    if ($outParam -eq $errParam) {
        throw "FATAL: Invocation $i at line $($call.Extent.StartLineNumber) uses identical stdout and stderr paths ($outParam)!"
    }
    Write-Host "  [OK] Distinct redirection verified." -ForegroundColor Green
}

Write-Host "`nALL $($startProcessCalls.Count) START-PROCESS INVOCATIONS VERIFIED CLEAN & DISTINCT!" -ForegroundColor Green

