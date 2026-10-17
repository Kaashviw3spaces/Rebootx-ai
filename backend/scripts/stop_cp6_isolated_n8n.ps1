# backend/scripts/stop_cp6_isolated_n8n.ps1
# Safely stops ONLY the isolated n8n process.
# Performs strict multi-attribute identity verification via WMI and network bindings.
# Fails closed without stopping anything if process ownership cannot be proven.
# Strictly guards against touching the shared n8n instance on port 5678.
param(
    [Parameter(Mandatory=$false)]
    [string]$PreparationDirectory
)

$ErrorActionPreference = 'Stop'
$backendDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not $PreparationDirectory) {
    $PreparationDirectory = Join-Path $backendDir '.temporal\cp6-prep-7163e9b9ff1143aeaa6e72939962467f'
}
$cp6Prep = (Resolve-Path -LiteralPath $PreparationDirectory).Path
$cp6InstancePath = Join-Path $cp6Prep 'isolated-n8n.json'
if (-not (Test-Path -LiteralPath $cp6InstancePath)) { throw "Isolated instance manifest missing: $cp6InstancePath" }

$cp6Instance = Get-Content -LiteralPath $cp6InstancePath -Raw | ConvertFrom-Json
$expectedPid = $cp6Instance.process_id
$isolatedDir = $cp6Instance.directory
$nodeExe = $cp6Instance.node_executable
$n8nBin = $cp6Instance.n8n_binary
$expectedOrigin = $cp6Instance.origin # http://127.0.0.1:5680
$expectedBrokerPort = $cp6Instance.broker_port # 5681

# 1. Inspect shared n8n on port 5678 (establish negative guardrail)
$sharedConns = Get-NetTCPConnection -LocalPort 5678 -State Listen -ErrorAction SilentlyContinue
$sharedPids = @($sharedConns | ForEach-Object { $_.OwningProcess } | Where-Object { $_ -gt 0 } | Select-Object -Unique)

# 2. Check listeners on isolated port 5680 and broker port 5681
$isolated5680Conns = Get-NetTCPConnection -LocalPort 5680 -State Listen -ErrorAction SilentlyContinue
$isolated5680Pids = @($isolated5680Conns | ForEach-Object { $_.OwningProcess } | Where-Object { $_ -gt 0 } | Select-Object -Unique)

$isolated5681Conns = Get-NetTCPConnection -LocalPort 5681 -State Listen -ErrorAction SilentlyContinue
$isolated5681Pids = @($isolated5681Conns | ForEach-Object { $_.OwningProcess } | Where-Object { $_ -gt 0 } | Select-Object -Unique)

# If nothing is listening on 5680, confirm port is already free
if ($isolated5680Pids.Count -eq 0) {
    Write-Host "[INFO] Port 5680 is not currently listening. Nothing to stop." -ForegroundColor Yellow
    exit 0
}

# 3. Guard against multiple or conflicting listeners
if ($isolated5680Pids.Count -ne 1) {
    throw "FAIL CLOSED: Ambiguous listeners detected on port 5680: $($isolated5680Pids -join ', ')"
}
$targetPid = $isolated5680Pids[0]

# 4. Strict guard: Target PID must NOT match shared instance
if ($sharedPids -contains $targetPid) {
    throw "FAIL CLOSED: Target PID $targetPid is associated with shared n8n port 5678! Refusing to touch."
}

# 5. Dual network binding proof: Isolated process must own BOTH 5680 AND 5681 (broker)
if (-not ($isolated5681Pids -contains $targetPid)) {
    throw "FAIL CLOSED: Process $targetPid listens on 5680 but does NOT own runner broker port 5681."
}

# 6. Deep WMI process identity verification
$cimProc = Get-CimInstance Win32_Process -Filter "ProcessId = $targetPid"
if (-not $cimProc) {
    throw "FAIL CLOSED: Unable to query process identity for PID $targetPid via WMI."
}

$procPath = $cimProc.ExecutablePath
$procCmd = $cimProc.CommandLine

Write-Host "Verifying process identity for PID $targetPid..." -ForegroundColor Cyan
Write-Host "  ExecutablePath: $procPath"
Write-Host "  CommandLine:    $procCmd"

# Check 6a: Executable must be node.exe
if ($procPath -notmatch '(?i)node\.exe$') {
    throw "FAIL CLOSED: Executable is '$procPath', expected node.exe."
}

# Check 6b: CommandLine must contain the exact cached n8n binary path
if ($procCmd -notmatch [regex]::Escape($n8nBin)) {
    throw "FAIL CLOSED: CommandLine does not match the configured isolated n8n binary path: $n8nBin"
}

# Check 6c: Validate isolated user folder and database existence
$dbPath = $cp6Instance.database_path
if (-not (Test-Path -LiteralPath $dbPath)) {
    throw "FAIL CLOSED: Isolated database path does not exist: $dbPath"
}
$stdoutLog = Join-Path $isolatedDir 'stdout.log'
if (-not (Test-Path -LiteralPath $stdoutLog)) {
    throw "FAIL CLOSED: Isolated log file missing: $stdoutLog"
}

# 7. Stop ONLY the verified isolated process
Write-Host "Stopping verified isolated n8n process (PID $targetPid)..." -ForegroundColor Yellow
Stop-Process -Id $targetPid -Force
Start-Sleep -Seconds 2

# 8. Post-stop verification
$postConns = Get-NetTCPConnection -LocalPort 5680 -State Listen -ErrorAction SilentlyContinue
if ($postConns) {
    throw "Port 5680 is still listening after stop attempt!"
}

# 9. Verify shared instance remains healthy
$postSharedConns = Get-NetTCPConnection -LocalPort 5678 -State Listen -ErrorAction SilentlyContinue
if (-not $postSharedConns) {
    throw "CRITICAL ALERT: Shared instance on port 5678 was unexpectedly affected!"
}

Write-Host "[SUCCESS] Isolated n8n process stopped cleanly. Port 5680 is free." -ForegroundColor Green
Write-Host "[OK] Shared n8n instance on port 5678 is intact and listening." -ForegroundColor Green
