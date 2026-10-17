# backend/scripts/run_cp6_live_recovery.ps1
# Operator-controlled, single-run end-to-end live recovery demonstration script.
# Implements strict verification gates, tracked PID management, fail-closed assertions,
# and a guaranteed finally-style cleanup path.
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

# 1. Resolve and validate absolute paths
$pythonExe = Join-Path $backendDir '.venv\Scripts\python.exe'
$temporalExe = Join-Path $backendDir '.temporal\cli\temporal.exe'
$manifestPath = Join-Path $cp6Prep 'manifest.json'
$instancePath = Join-Path $cp6Prep 'isolated-n8n.json'
$secretsPath = Join-Path $cp6Prep 'secrets.dpapi'

if (-not (Test-Path -LiteralPath $pythonExe)) { throw "Python executable not found at: $pythonExe" }
if (-not (Test-Path -LiteralPath $temporalExe)) { throw "Temporal CLI executable not found at: $temporalExe" }
if (-not (Test-Path -LiteralPath $manifestPath)) { throw "Manifest missing at: $manifestPath" }
if (-not (Test-Path -LiteralPath $instancePath)) { throw "Isolated instance manifest missing: $instancePath" }

$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$instance = Get-Content -LiteralPath $instancePath -Raw | ConvertFrom-Json
$apiKeyPath = Join-Path $instance.directory 'api-key.dpapi'

if (-not (Test-Path -LiteralPath $apiKeyPath)) { throw "API key file missing: $apiKeyPath" }

# Decrypt credentials in memory
$cp6Secrets = [Net.NetworkCredential]::new('', (ConvertTo-SecureString (Get-Content -LiteralPath $secretsPath -Raw))).Password | ConvertFrom-Json
$cp6ApiKey = [Net.NetworkCredential]::new('', (ConvertTo-SecureString (Get-Content -LiteralPath $apiKeyPath -Raw))).Password
$headers = @{ 'X-N8N-API-KEY' = $cp6ApiKey }

# Tracked child process handles
$trackedProcesses = @{}
$cleanupSuccess = $true

function Stop-TrackedProcess([string]$name, [System.Diagnostics.Process]$proc, [string]$expectedPattern) {
    if (-not $proc) { return $true }
    try {
        if ($proc.HasExited) { return $true }
        $pidToStop = $proc.Id
        $cim = Get-CimInstance Win32_Process -Filter "ProcessId = $pidToStop" -ErrorAction SilentlyContinue
        if ($cim -and $cim.CommandLine -match $expectedPattern) {
            Write-Host "Stopping verified $name (PID $pidToStop)..." -ForegroundColor Yellow
            Stop-Process -Id $pidToStop -Force
            Start-Sleep -Milliseconds 500
            return $true
        } else {
            Write-Warning "Refusing to stop $name (PID $pidToStop): CommandLine does not match expected pattern '$expectedPattern'."
            if ($cim) { Write-Warning "Actual CommandLine: $($cim.CommandLine)" }
            return $false
        }
    } catch {
        Write-Warning "Failed to stop $name process: $($_.Exception.Message)"
        return $false
    }
}

try {
    Write-Host "=================================================================" -ForegroundColor Cyan
    Write-Host " REBOOTX CHECKPOINT 6 -- OPERATOR-CONTROLLED LIVE RECOVERY TEST" -ForegroundColor Cyan
    Write-Host "=================================================================" -ForegroundColor Cyan

    # --- GATE 1: PRE-FLIGHT READ-ONLY HEALTH & ISOLATION CHECKS ---
    Write-Host "`n[GATE 1] Running pre-flight system health checks..." -ForegroundColor Cyan

    # 1a. Shared n8n on port 5678 check
    $sharedConns = Get-NetTCPConnection -LocalPort 5678 -State Listen -ErrorAction SilentlyContinue
    if (-not $sharedConns) { throw "FAIL: Shared n8n on port 5678 is not running!" }
    $sharedHealth = Invoke-WebRequest -Uri 'http://127.0.0.1:5678/healthz' -UseBasicParsing -TimeoutSec 2
    if ($sharedHealth.StatusCode -ne 200) { throw "FAIL: Shared n8n /healthz returned $($sharedHealth.StatusCode)" }
    Write-Host "  [OK] Shared n8n on port 5678 is healthy and untouched." -ForegroundColor Green

    # 1b. Isolated n8n on port 5680 check
    $isoHealth = Invoke-WebRequest -Uri 'http://127.0.0.1:5680/healthz' -UseBasicParsing -TimeoutSec 2
    if ($isoHealth.StatusCode -ne 200) { throw "FAIL: Isolated n8n /healthz returned $($isoHealth.StatusCode)" }
    Write-Host "  [OK] Isolated n8n on port 5680 is healthy." -ForegroundColor Green

    # 1c. Mock provider on port 8011 check
    $provHealth = Invoke-WebRequest -Uri 'http://127.0.0.1:8011/openapi.json' -UseBasicParsing -TimeoutSec 2
    if ($provHealth.StatusCode -ne 200) { throw "FAIL: Demo provider on port 8011 is not running!" }
    Write-Host "  [OK] Demo provider on port 8011 is available." -ForegroundColor Green

    # 1d. Confirm calibration execution 1 is intact and untouched
    $exec1 = Invoke-RestMethod -Uri 'http://127.0.0.1:5680/api/v1/executions/1?includeData=true' -Headers $headers -Method Get
    if ($exec1.id -ne 1 -or $exec1.workflowId -ne 'ievg2u7YcfdnU3L8' -or $exec1.status -ne 'error' -or $exec1.retryOf) {
        throw "FAIL: Calibration execution 1 is corrupted or was modified!"
    }
    Write-Host "  [OK] Calibration execution 1 confirmed intact (Status: error, Unretried)." -ForegroundColor Green

    # 1e. Confirm ports 8000 and 7233 are currently free
    foreach ($p in @(8000, 7233)) {
        $c = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
        if ($c) { throw "FAIL: Port $p is already in use by PID $($c.OwningProcess)! Must be free before starting." }
    }
    Write-Host "  [OK] Ports 8000 and 7233 are free." -ForegroundColor Green

    # --- GATE 2: CONFIGURE UNIFIED ENVIRONMENT & START SERVICES ---
    Write-Host "`n[GATE 2] Configuring unified session environment..." -ForegroundColor Cyan

    $verifiedSha256 = '34562e136ce84efed16d4faa31d28e62d10613cb8c363c51e3a372791c12526b'
    $authObj = @{
        tenant_id = '0610d06e-460f-465e-8b19-f80b336fd8e7'
        integration_id = '38979968-2d1f-4fd0-9307-c829e54ba58f'
        workflow_external_id = 'ievg2u7YcfdnU3L8'
        operation = 'retry_execution'
        idempotent = $true
        side_effect_safe = $true
        workflow_sha256 = $verifiedSha256
    }
    # In Windows PowerShell 5.1, ConvertTo-Json unrolls single-element arrays passed via the pipeline.
    # Passing the array via -InputObject preserves the array structure.
    $authJson = ConvertTo-Json -InputObject @($authObj) -Compress
    if (-not $authJson.StartsWith('[') -or -not $authJson.EndsWith(']')) {
        throw "Serialization error: N8N_AUTHORIZATIONS must be a JSON array, got: $authJson"
    }

    $env:DATABASE_URL = $manifest.database_url
    $env:TEMPORAL_TASK_QUEUE = $manifest.temporal_task_queue
    $env:TEMPORAL_ADDRESS = '127.0.0.1:7233'
    $env:TEMPORAL_NAMESPACE = 'default'
    $env:CP6_DEMO_WEBHOOK_SECRET = $cp6Secrets.signing_secret
    $env:REBOOTX_WEBHOOK_SECRET = $cp6Secrets.signing_secret
    $env:RECOVERY_MODE = 'real_n8n'
    $env:N8N_BASE_URL = 'http://127.0.0.1:5680'
    $env:N8N_SUPPORTED_VERSION = '2.43.6'
    $env:N8N_API_KEY = $cp6ApiKey
    $env:AI_PROVIDER = 'mock'
    $env:N8N_AUTHORIZATIONS = $authJson
    $env:PYTHONPATH = $backendDir

    # Hard guard in Python: assert driver is SQLite and directory is isolated demo.db
    & $pythonExe -B -m scripts.verify_cp6_recovery --check-isolation
    if ($LASTEXITCODE -ne 0) { throw "FAIL: Database isolation assertion failed!" }
    Write-Host "  [OK] Database isolation verified (sqlite:///.../demo.db)." -ForegroundColor Green

    # Start 1: Temporal Server
    Write-Host "Starting Temporal server (port 7233)..." -ForegroundColor Cyan
    $temporalLogOut = Join-Path $cp6Prep 'temporal-server.stdout.log'
    $temporalLogErr = Join-Path $cp6Prep 'temporal-server.stderr.log'
    $temporalDb = Join-Path $backendDir '.temporal\rebootx-server.db'

    # Ensure log directories exist before starting processes
    if (-not (Test-Path -LiteralPath $cp6Prep)) { New-Item -ItemType Directory -Path $cp6Prep -Force | Out-Null }
    $temporalDbDir = [System.IO.Path]::GetDirectoryName($temporalDb)
    if (-not (Test-Path -LiteralPath $temporalDbDir)) { New-Item -ItemType Directory -Path $temporalDbDir -Force | Out-Null }

    # Validate distinct redirection paths before launching
    if ($temporalLogOut -eq $temporalLogErr) { throw "Invalid configuration: temporal stdout and stderr log paths are identical!" }
    $trackedProcesses['Temporal'] = Start-Process -FilePath $temporalExe -ArgumentList @('server', 'start-dev', '--ip', '127.0.0.1', '--db-filename', $temporalDb) -WorkingDirectory $backendDir -WindowStyle Hidden -RedirectStandardOutput $temporalLogOut -RedirectStandardError $temporalLogErr -PassThru

    # Wait for Temporal port 7233
    $temporalReady = $false
    for ($i = 0; $i -lt 15; $i++) {
        Start-Sleep -Seconds 1
        if (Get-NetTCPConnection -LocalPort 7233 -State Listen -ErrorAction SilentlyContinue) {
            $temporalReady = $true
            break
        }
    }
    if (-not $temporalReady) { throw "Temporal server failed to start within 15 seconds! Check $temporalLogErr" }
    Write-Host "  [OK] Temporal server running (PID $($trackedProcesses['Temporal'].Id))." -ForegroundColor Green

    # Start 2: Recovery Worker
    Write-Host "Starting Recovery Worker..." -ForegroundColor Cyan
    $workerLogOut = Join-Path $cp6Prep 'temporal-worker.stdout.log'
    $workerLogErr = Join-Path $cp6Prep 'temporal-worker.stderr.log'
    if ($workerLogOut -eq $workerLogErr) { throw "Invalid configuration: worker stdout and stderr log paths are identical!" }
    $trackedProcesses['Worker'] = Start-Process -FilePath $pythonExe -ArgumentList @('-B', '-m', 'app.temporal.worker') -WorkingDirectory $backendDir -WindowStyle Hidden -RedirectStandardOutput $workerLogOut -RedirectStandardError $workerLogErr -PassThru
    Start-Sleep -Seconds 2
    if ($trackedProcesses['Worker'].HasExited) { throw "Recovery worker process exited immediately! Check $workerLogErr" }
    Write-Host "  [OK] Recovery worker running (PID $($trackedProcesses['Worker'].Id))." -ForegroundColor Green

    # Start 3: Outbox Dispatcher
    Write-Host "Starting Outbox Dispatcher..." -ForegroundColor Cyan
    $dispatcherLogOut = Join-Path $cp6Prep 'temporal-dispatcher.stdout.log'
    $dispatcherLogErr = Join-Path $cp6Prep 'temporal-dispatcher.stderr.log'
    if ($dispatcherLogOut -eq $dispatcherLogErr) { throw "Invalid configuration: dispatcher stdout and stderr log paths are identical!" }
    $trackedProcesses['Dispatcher'] = Start-Process -FilePath $pythonExe -ArgumentList @('-B', '-m', 'app.temporal.dispatcher') -WorkingDirectory $backendDir -WindowStyle Hidden -RedirectStandardOutput $dispatcherLogOut -RedirectStandardError $dispatcherLogErr -PassThru
    Start-Sleep -Seconds 2
    if ($trackedProcesses['Dispatcher'].HasExited) { throw "Dispatcher process exited immediately! Check $dispatcherLogErr" }
    Write-Host "  [OK] Outbox dispatcher running (PID $($trackedProcesses['Dispatcher'].Id))." -ForegroundColor Green

    # Start 4: FastAPI Backend
    Write-Host "Starting FastAPI Backend (port 8000)..." -ForegroundColor Cyan
    $fastapiLogOut = Join-Path $cp6Prep 'fastapi.stdout.log'
    $fastapiLogErr = Join-Path $cp6Prep 'fastapi.stderr.log'
    if ($fastapiLogOut -eq $fastapiLogErr) { throw "Invalid configuration: fastapi stdout and stderr log paths are identical!" }
    $trackedProcesses['FastAPI'] = Start-Process -FilePath $pythonExe -ArgumentList @('-B', '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000') -WorkingDirectory $backendDir -WindowStyle Hidden -RedirectStandardOutput $fastapiLogOut -RedirectStandardError $fastapiLogErr -PassThru

    # Wait for FastAPI port 8000 /health
    $apiReady = $false
    for ($i = 0; $i -lt 15; $i++) {
        Start-Sleep -Seconds 1
        try {
            $h = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/health' -UseBasicParsing -TimeoutSec 2
            if ($h.StatusCode -eq 200) { $apiReady = $true; break }
        } catch { }
    }
    if (-not $apiReady) { throw "FastAPI failed to start within 15 seconds! Check $fastapiLogErr" }
    Write-Host "  [OK] FastAPI running (PID $($trackedProcesses['FastAPI'].Id))." -ForegroundColor Green

    # --- GATE 3: ACTIVATE BOTH ISOLATED WORKFLOWS ---
    Write-Host "`n[GATE 3] Activating isolated workflows on port 5680..." -ForegroundColor Cyan

    Write-Host "  Activating Error Handler (wmtArUNSGBtEuCUM)..."
    $actError = Invoke-RestMethod -Uri 'http://127.0.0.1:5680/api/v1/workflows/wmtArUNSGBtEuCUM/activate' -Method Post -Headers $headers -ContentType 'application/json' -Body '{}'
    if (-not $actError.active) { throw "Failed to activate error handler workflow!" }

    Write-Host "  Activating Demo Workflow (ievg2u7YcfdnU3L8)..."
    $actDemo = Invoke-RestMethod -Uri 'http://127.0.0.1:5680/api/v1/workflows/ievg2u7YcfdnU3L8/activate' -Method Post -Headers $headers -ContentType 'application/json' -Body '{}'
    if (-not $actDemo.active) { throw "Failed to activate demo workflow!" }
    Write-Host "  [OK] Both workflows active on port 5680." -ForegroundColor Green

    # Wait for n8n production webhook listener to complete registration.
    # Note: A GET request to a POST-only webhook is guaranteed NOT to execute the workflow nodes.
    # When unregistered, n8n returns 404: "The requested webhook 'GET ...' is not registered."
    # When registered for POST, n8n detects the path and returns 404: "This webhook is not registered for GET requests. Did you mean to make a POST request?"
    Write-Host "  Verifying webhook registration readiness on port 5680..." -ForegroundColor Cyan
    $webhookReady = $false
    for ($wCheck = 1; $wCheck -le 15; $wCheck++) {
        Start-Sleep -Seconds 1
        $probeReq = [System.Net.HttpWebRequest]::Create('http://127.0.0.1:5680/webhook/rebootx-safe-demo')
        $probeReq.Method = 'GET'
        $probeReq.Timeout = 2000
        try {
            $probeResp = $probeReq.GetResponse()
            # If 200 returned, route is definitely registered
            $webhookReady = $true
            $probeResp.Close()
            break
        } catch [System.Net.WebException] {
            $errResp = $_.Exception.Response
            if ($errResp) {
                $stream = $errResp.GetResponseStream()
                $reader = [System.IO.StreamReader]::new($stream)
                $bodyText = $reader.ReadToEnd()
                $errResp.Close()
                if ($bodyText -match 'Did you mean to make a POST request') {
                    $webhookReady = $true
                    break
                }
            }
        } catch { }
    }
    if (-not $webhookReady) {
        throw "Failed to verify webhook readiness: /webhook/rebootx-safe-demo remained unregistered after 15 seconds!"
    }
    Write-Host "  [OK] Production webhook /webhook/rebootx-safe-demo is registered and ready." -ForegroundColor Green

    # --- GATE 4: SUBMIT CONTROLLED LIVE DEMONSTRATION WEBHOOK ---
    $liveRunId = [guid]::NewGuid().ToString()
    Write-Host "`n[GATE 4] Triggering controlled failure with fresh UUID: $liveRunId..." -ForegroundColor Yellow

    $body = @{ run_id = $liveRunId } | ConvertTo-Json
    $webhookResp = Invoke-RestMethod -Uri 'http://127.0.0.1:5680/webhook/rebootx-safe-demo' -Method Post -ContentType 'application/json' -Body $body
    Write-Host "  [OK] Webhook accepted by n8n. Live pipeline initiated." -ForegroundColor Green

    # --- GATE 5: MONITORING & INDEPENDENT VERIFICATION LOOP ---
    Write-Host "`n[GATE 5] Monitoring pipeline: failure ingestion -> Temporal recovery -> retry execution..." -ForegroundColor Cyan

    $retriedExec = $null
    $failedExecId = $null

    for ($attempt = 1; $attempt -le 25; $attempt++) {
        Start-Sleep -Seconds 2
        $execList = (Invoke-RestMethod -Uri 'http://127.0.0.1:5680/api/v1/executions' -Headers $headers -Method Get).data
        $demoExecs = @($execList | Where-Object { $_.workflowId -eq 'ievg2u7YcfdnU3L8' } | Sort-Object id -Descending)

        # Identify newly failed execution (must be > 1 to never touch calibration execution 1)
        if (-not $failedExecId) {
            $newFailed = $demoExecs | Where-Object { $_.id -gt 1 -and $_.status -eq 'error' -and -not $_.retryOf } | Select-Object -First 1
            if ($newFailed) {
                $failedExecId = $newFailed.id
                Write-Host "  [OK] Captured New Failed Execution ID: $failedExecId (Status: error)" -ForegroundColor Green
            }
        }

        # Check for resulting retry execution
        if ($failedExecId) {
            $retryCandidate = $demoExecs | Where-Object { $_.retryOf -eq $failedExecId } | Select-Object -First 1
            if ($retryCandidate) {
                Write-Host "  [POLL] Detected Retry Execution ID $($retryCandidate.id) (Status: $($retryCandidate.status))..." -ForegroundColor Cyan
                if ($retryCandidate.status -eq 'success') {
                    $retriedExec = $retryCandidate
                    break
                }
            }
        }
    }

    if (-not $retriedExec) {
        throw "Verification timeout: Retried execution did not reach terminal status 'success' within 50 seconds!"
    }

    Write-Host "`n=================================================================" -ForegroundColor Green
    Write-Host " CERTIFIED RECOVERY PROVENANCE EVIDENCE" -ForegroundColor Green
    Write-Host "=================================================================" -ForegroundColor Green
    Write-Host "n8n Provider Executions:" -ForegroundColor Cyan
    Write-Host "  Original Failed Execution ID: $($retriedExec.retryOf)"
    Write-Host "  Resulting Retried ID:         $($retriedExec.id)"
    Write-Host "  Resulting Terminal Status:    $($retriedExec.status)"
    Write-Host "  Workflow ID:                  $($retriedExec.workflowId)"

    # --- GATE 6: VERIFY REBOOTX PERSISTED INCIDENT STATE ---
    & $pythonExe -B -m scripts.verify_cp6_recovery --check-provenance
    if ($LASTEXITCODE -ne 0) { throw "FAIL: REBOOTX database verification assertion failed!" }

    Write-Host "`n[SUCCESS] Checkpoint 6 Live Recovery Demonstration FULLY VERIFIED!" -ForegroundColor Green

}
finally {
    Write-Host "`n=================================================================" -ForegroundColor Yellow
    Write-Host " FINALLY: EXECUTING SAFE CLEANUP AND ROLLBACK" -ForegroundColor Yellow
    Write-Host "=================================================================" -ForegroundColor Yellow

    # 1. Deactivate isolated workflows
    try {
        Write-Host "Deactivating demo workflow (ievg2u7YcfdnU3L8)..." -ForegroundColor Yellow
        Invoke-RestMethod -Uri 'http://127.0.0.1:5680/api/v1/workflows/ievg2u7YcfdnU3L8/deactivate' -Method Post -Headers $headers -ContentType 'application/json' -Body '{}' -ErrorAction Stop | Out-Null
        Write-Host "  [OK] Demo workflow deactivated." -ForegroundColor Green
    } catch {
        Write-Warning "Failed to deactivate demo workflow: $($_.Exception.Message)"
    }

    try {
        Write-Host "Deactivating error handler (wmtArUNSGBtEuCUM)..." -ForegroundColor Yellow
        Invoke-RestMethod -Uri 'http://127.0.0.1:5680/api/v1/workflows/wmtArUNSGBtEuCUM/deactivate' -Method Post -Headers $headers -ContentType 'application/json' -Body '{}' -ErrorAction Stop | Out-Null
        Write-Host "  [OK] Error handler deactivated." -ForegroundColor Green
    } catch {
        Write-Warning "Failed to deactivate error handler workflow: $($_.Exception.Message)"
    }

    # 2. Stop tracked processes by PID with WMI CommandLine verification
    if (-not (Stop-TrackedProcess 'FastAPI' $trackedProcesses['FastAPI'] 'uvicorn app.main:app')) { $cleanupSuccess = $false }
    if (-not (Stop-TrackedProcess 'Dispatcher' $trackedProcesses['Dispatcher'] 'app.temporal.dispatcher')) { $cleanupSuccess = $false }
    if (-not (Stop-TrackedProcess 'Worker' $trackedProcesses['Worker'] 'app.temporal.worker')) { $cleanupSuccess = $false }
    if (-not (Stop-TrackedProcess 'Temporal' $trackedProcesses['Temporal'] 'temporal.*server')) { $cleanupSuccess = $false }

    # 3. Restore session environment to mock-only
    $env:RECOVERY_MODE = 'mock-only'
    $env:N8N_AUTHORIZATIONS = '[]'
    Remove-Item Env:CP6_DEMO_WEBHOOK_SECRET, Env:REBOOTX_WEBHOOK_SECRET, Env:N8N_API_KEY -ErrorAction SilentlyContinue
    Remove-Variable cp6Secrets, cp6ApiKey, headers -ErrorAction SilentlyContinue

    # 4. Verify shared instance on port 5678 is still healthy
    try {
        $sharedFinal = Invoke-WebRequest -Uri 'http://127.0.0.1:5678/healthz' -UseBasicParsing -TimeoutSec 2
        if ($sharedFinal.StatusCode -eq 200) {
            Write-Host "  [OK] Shared n8n on port 5678 is healthy and running." -ForegroundColor Green
        }
    } catch {
        Write-Warning "Shared n8n health check failed: $($_.Exception.Message)"
    }
    if ($cleanupSuccess) {
        Write-Host 'CLEANUP COMPLETE: Environment reverted to mock-only.' -ForegroundColor Green
    } else {
        Write-Warning 'CLEANUP INCOMPLETE: One or more tracked processes could not be verified or stopped.'
    }
}

