# backend/scripts/restart_cp6_isolated_n8n.ps1
# Restarts ONLY the existing isolated n8n instance using its existing directory and database.
# Preserves the owner account, encryption key, and saved API key.
# Loads the repaired process-environment.dpapi.
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
$cp6Folder = $cp6Instance.directory
$cp6Node = $cp6Instance.node_executable
$cp6N8n = $cp6Instance.n8n_binary
$cp6ProcessEnvPath = Join-Path $cp6Folder 'process-environment.dpapi'

if (-not (Test-Path -LiteralPath $cp6Folder)) { throw "Isolated folder missing: $cp6Folder" }
if (-not (Test-Path -LiteralPath $cp6ProcessEnvPath)) { throw "process-environment.dpapi missing: $cp6ProcessEnvPath" }

# 1. Verify ports 5680 & 5681 are free
foreach ($port in @(5680, 5681)) {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($conn) { throw "Port $port is already occupied by PID $($conn.OwningProcess); refusing to start." }
}

# 2. Guard: Verify shared instance on port 5678 is running and untouched
$sharedConns = Get-NetTCPConnection -LocalPort 5678 -State Listen -ErrorAction SilentlyContinue
if (-not $sharedConns) { throw "WARNING: Shared n8n on port 5678 is not detected." }

# 3. Decrypt repaired process environment using Windows DPAPI
$cp6Protected = ConvertTo-SecureString ([System.IO.File]::ReadAllText($cp6ProcessEnvPath))
$cp6Environment = [System.Net.NetworkCredential]::new('', $cp6Protected).Password | ConvertFrom-Json

# 4. Launch isolated n8n process with repaired environment
$cp6OldEnvironment = @{}
foreach ($item in [Environment]::GetEnvironmentVariables('Process').GetEnumerator()) {
    $cp6OldEnvironment[$item.Key] = $item.Value
}

try {
    foreach ($name in @([Environment]::GetEnvironmentVariables('Process').Keys)) {
        [Environment]::SetEnvironmentVariable($name, $null, 'Process')
    }
    foreach ($prop in $cp6Environment.PSObject.Properties) {
        [Environment]::SetEnvironmentVariable($prop.Name, [string]$prop.Value, 'Process')
    }
    
    Write-Host "Starting isolated n8n from existing directory: $cp6Folder..." -ForegroundColor Cyan
    $newProc = Start-Process -FilePath $cp6Node -ArgumentList @(('"' + $cp6N8n + '"'), 'start') -WorkingDirectory $cp6Folder -WindowStyle Hidden -RedirectStandardOutput (Join-Path $cp6Folder 'stdout.log') -RedirectStandardError (Join-Path $cp6Folder 'stderr.log') -PassThru
}
finally {
    # Restore launcher process environment
    foreach ($name in @([Environment]::GetEnvironmentVariables('Process').Keys)) {
        [Environment]::SetEnvironmentVariable($name, $null, 'Process')
    }
    foreach ($name in $cp6OldEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $cp6OldEnvironment[$name], 'Process')
    }
    Remove-Variable cp6Protected, cp6Environment -ErrorAction SilentlyContinue
}

# 5. Update process_id in isolated-n8n.json
$cp6Instance.process_id = $newProc.Id
[System.IO.File]::WriteAllText($cp6InstancePath, ($cp6Instance | ConvertTo-Json -Depth 5))

# 6. Poll for readiness on http://127.0.0.1:5680/healthz (up to 20 seconds)
Write-Host "Waiting for isolated n8n to respond on http://127.0.0.1:5680/healthz (PID: $($newProc.Id))..." -ForegroundColor Cyan
$ready = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 1
    try {
        $resp = Invoke-WebRequest -Uri 'http://127.0.0.1:5680/healthz' -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($resp.StatusCode -eq 200) {
            $ready = $true
            break
        }
    } catch { }
}

if (-not $ready) {
    throw "Isolated n8n failed to respond on port 5680 within 20 seconds. Check $($cp6Folder)\stderr.log."
}

# 7. Final assertion: confirm shared instance on 5678 is STILL listening and untouched
$postShared = Get-NetTCPConnection -LocalPort 5678 -State Listen -ErrorAction SilentlyContinue
if (-not $postShared) {
    throw "CRITICAL ALERT: Shared instance on port 5678 was unexpectedly affected!"
}

Write-Host "[SUCCESS] Isolated n8n restarted successfully on PID $($newProc.Id)." -ForegroundColor Green
Write-Host "[OK] http://127.0.0.1:5680/healthz returned HTTP 200." -ForegroundColor Green
Write-Host "[OK] Shared n8n on port 5678 is untouched and running." -ForegroundColor Green

