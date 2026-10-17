# Checkpoint 6 live-demo preflight

Read-only inspection: October 17, 2026 (Asia/Calcutta). **Not ready to trigger recovery.** No workflow was triggered, no recovery endpoint was called, no credentials were changed, and no application records or migrations were written during this inspection. The commands below are proposed next steps and were not executed.

## Verified current state

| Check | Observed result |
| --- | --- |
| API key | Present in `backend/.env`; no process-environment override. Value never displayed. |
| n8n origin | `http://127.0.0.1:5678`, reachable. Supported-version setting is `2.43.6`. |
| Authentication and workflow read | Public API GET returned HTTP 200 for `ievg2u7YcfdnU3L8` and its selected error workflow. |
| Execution list/read | Execution list returned HTTP 200. A separate metadata-only GET of an existing execution returned HTTP 200, establishing execution-read access. |
| Retry permission | **Not independently verified.** No retry POST was made. The documented API has no read-only current-key scope introspection endpoint in the inspected specification. Scope information is stored server-side, not in the API-key JWT. No authenticated browser session was exposed by the available browser tool. |
| Actual demo workflow | `ievg2u7YcfdnU3L8`, named `REBOOTX Side Effect Safe Recovery Demo`, published/active. |
| Error Workflow selection | `wmtArUNSGBtEuCUM`, named `REBOOTX Error Handler`, active. |
| Demo actions | Two nodes: POST Webhook `rebootx-safe-demo` and HTTP POST to the exact local `/probe/` expression from the template. HTTP timeout 5000 ms, node retries disabled, no node credentials. Connections match the template. |
| Import normalization | The Webhook omits `responseMode`; installed n8n Webhook code defines default `onReceived`. This explains the initial raw-template mismatch and is not an extra external action. |
| Effective backend database | `backend/.env` selects PostgreSQL/Neon database `neondb`, host `ep-polished-rain-ao2wb2hc.c-2.ap-southeast-1.aws.neon.tech`, schema `public`. No DATABASE_URL process override. Username, password and connection parameters omitted. |
| Effective database migration | **0003**. The three CP6 columns are absent. A successful explicit READ ONLY transaction confirmed this. The sandbox initially denied connectivity; the read-only check succeeded with the required access. |
| Effective database registration | No joined tenant/integration/workflow registrations. No incidents or outbox records. No existing IDs can be used to build a CP6 authorization. |
| Older local demo database | `.temporal/live_demo.db`, opened with SQLite `mode=ro`: revision **0003**, one old `notify-orders` / `notification_v1` registration, one historical RECOVERED incident and zero pending outbox rows. It is not selected by the current backend settings and is not registered for the new workflow. It was not modified. |
| Recovery mode / authorization | `mock-only`; `N8N_AUTHORIZATIONS=[]`. |
| Saved demo snapshot | No executions exist for `ievg2u7YcfdnU3L8`. Therefore no failed-execution `workflowData` hash can yet be established. The workflow GET object hash is deliberately not used as authorization. |
| Signing configuration | No webhook-secret variable is present in `backend/.env`. Current Error Handler code still resolves runtime variables, with fallback integration UUID all-zero, workflow alias `notify-orders`, and empty signing secret. Its current process/$vars values cannot be established from public workflow configuration. The documented GET `/api/v1/variables` returned **403**, so variable overrides could not be inspected. Correct runtime signing is **unverified**. |
| Demo provider | Port 8011 is listening. GET `/openapi.json` returned 200 with the expected provider title and `/probe/{run_id}` route. No POST was sent and no first-failure counter was consumed. |
| Other services | FastAPI 8000, Temporal 7233/UI 8233 and dashboard 5173 were closed. No worker or dispatcher was started. Native Temporal executable exists. |

The old local integration is not an authorization for the new workflow. The intended demo database cannot be inferred from the existence of old files. The commands below deliberately select a **new isolated local SQLite database**, keeping both existing databases unchanged.

## Before running the proposed commands

Verify the existing key's `execution:retry` scope and its user's project `workflow:execute` access in n8n's API-key/project settings. `execution:read` is already proven; the helper commands also use workflow-read access already proven. A successful GET does not establish retry permission. Do not generate/rotate a key or expand permissions as part of this preflight without an explicit operator decision.

The existing Error Handler reads integration/signing/workflow settings from n8n's process environment or `$vars`. The following proposal starts a dedicated **demo session of the same existing local n8n instance**, retaining the actual imported workflow ID. Stop the existing n8n process yourself with Ctrl+C in its terminal before restarting it; do not start a second process against the same n8n database. Do not use this environment override on an instance whose other automations depend on that shared handler configuration. If `$vars` defines any of these REBOOTX names, it takes precedence over environment values; resolve that conflict explicitly before proceeding.

No existing credential value is overwritten on disk. A new demo-only signing secret is generated in the controller process and inherited by the demo backend/n8n children. Environment access by Code nodes is required by this existing handler design; enabling it exposes the n8n process environment to workflow code, so use the controlled demo session only. Do not print the secret or include it in workflow exports.

## 1. Prepare a fresh isolated backend target

Run in a new PowerShell controller terminal and keep it open. These commands create a **new** CP6 database when you choose to execute them. They do not migrate Neon or the older local demo file.

```powershell
$cp6Root = 'C:\Users\Saksham\OneDrive\Desktop\Rebootx-ai'
$cp6Backend = Join-Path $cp6Root 'backend'
$cp6Python = Join-Path $cp6Backend '.venv\Scripts\python.exe'
Set-Location -LiteralPath $cp6Backend

$cp6Session = [guid]::NewGuid().ToString('N')
$cp6Db = Join-Path $cp6Backend ".temporal\cp6-demo-$cp6Session.db"
if (Test-Path -LiteralPath $cp6Db) { throw 'Refusing to reuse an existing database' }
$env:DATABASE_URL = 'sqlite:///' + $cp6Db.Replace('\', '/')
$env:RECOVERY_MODE = 'mock-only'
$env:N8N_AUTHORIZATIONS = '[]'
$env:N8N_BASE_URL = 'http://127.0.0.1:5678'
$env:N8N_SUPPORTED_VERSION = '2.43.6'
$env:AI_PROVIDER = 'mock'
$env:TEMPORAL_ADDRESS = '127.0.0.1:7233'
$env:TEMPORAL_NAMESPACE = 'default'
$env:TEMPORAL_TASK_QUEUE = "rebootx-cp6-$cp6Session"
$env:TEMPORAL_API_KEY = ''
$env:TEMPORAL_TLS_ENABLED = 'false'

$cp6Bytes = New-Object byte[] 32
$cp6Rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$cp6Rng.GetBytes($cp6Bytes)
$cp6Rng.Dispose()
$env:CP6_DEMO_WEBHOOK_SECRET = [Convert]::ToBase64String($cp6Bytes)

& $cp6Python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Migration failed; stop' }
& $cp6Python -m alembic current
if ($LASTEXITCODE -ne 0) { throw 'Migration status check failed; stop' }

$cp6Provision = & $cp6Python -m scripts.provision --tenant-name 'CP6 Safe Demo' --workflow-external-id 'ievg2u7YcfdnU3L8' --workflow-kind side_effect_safe_demo_v1 --secret-env CP6_DEMO_WEBHOOK_SECRET
if ($LASTEXITCODE -ne 0) { throw 'Provisioning failed; stop' }
$cp6ProvisionText = $cp6Provision -join "`n"
$cp6Tenant = [regex]::Match($cp6ProvisionText, 'Tenant ID: ([0-9a-f-]{36})').Groups[1].Value
$cp6Integration = [regex]::Match($cp6ProvisionText, 'Integration ID: ([0-9a-f-]{36})').Groups[1].Value
if (-not $cp6Tenant -or -not $cp6Integration) { throw 'Actual provisioned IDs were not returned; stop' }
[guid]::Parse($cp6Tenant) | Out-Null
[guid]::Parse($cp6Integration) | Out-Null
```

`scripts.provision` prompts privately for the new tenant read token. Supply a securely generated token of at least 32 characters and retain it privately for dashboard login. It is separate from the existing n8n API key and is not included in this report. The actual tenant/integration IDs above come from the new transaction's output; none are guessed.

## 2. Configure the dedicated n8n demo session

After stopping the currently running local n8n process in its original terminal, use the same controller shell. The existing provider on 8011 can stay running. Do not start FastAPI, the worker or dispatcher during calibration.

```powershell
$env:REBOOTX_BASE_URL = 'http://127.0.0.1:8000'
$env:REBOOTX_INTEGRATION_ID = $cp6Integration
$env:REBOOTX_WEBHOOK_SECRET = $env:CP6_DEMO_WEBHOOK_SECRET
$env:REBOOTX_WORKFLOW_EXTERNAL_ID = 'ievg2u7YcfdnU3L8'
$env:N8N_BLOCK_ENV_ACCESS_IN_NODE = 'false'

$cp6N8n = Join-Path $env:LOCALAPPDATA 'npm-cache\_npx\a8a7eec953f1f314\node_modules\n8n\bin\n8n'
if (-not (Test-Path -LiteralPath $cp6N8n)) { throw 'Inspected n8n binary missing; stop' }
$cp6N8nProcess = Start-Process -FilePath 'node.exe' -ArgumentList @(('"' + $cp6N8n + '"'), 'start') -WorkingDirectory $cp6Backend -WindowStyle Hidden -PassThru
```

Wait for n8n to be available, then confirm the existing workflow and selected Error Workflow remain published in its UI. No workflow content/settings/credentials are changed by these commands. If the Code node cannot read the configured environment or `$vars` overrides it, stop and fix that explicitly before an ingestion test.

## 3. Calibration and the exact saved-workflow hash

**This section deliberately triggers only a calibration failure when the operator runs it. It was not run during preflight.** FastAPI must remain stopped so this failure does not enter the recovery queue. The existing handler HTTP node has no automatic node retry; wait for its failed delivery to finish in n8n before starting FastAPI. Never manually redeliver this calibration event.

```powershell
if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) { throw 'Stop FastAPI before calibration' }
$cp6CalibrationRun = [guid]::NewGuid().ToString()
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:5678/webhook/rebootx-safe-demo' -ContentType 'application/json' -Body (@{run_id=$cp6CalibrationRun} | ConvertTo-Json)

# In n8n, open the failed production execution of workflow ievg2u7YcfdnU3L8.
# Confirm its Webhook body run_id equals $cp6CalibrationRun and its only failure is the local probe's first 503.
$cp6CalibrationExecution = Read-Host 'Actual failed calibration execution ID from n8n'
if ($cp6CalibrationExecution -notmatch '^[1-9][0-9]{0,19}$') { throw 'Invalid execution ID; stop' }
$cp6HashOutput = & $cp6Python -m scripts.n8n_fingerprint --execution-id $cp6CalibrationExecution --workflow-id 'ievg2u7YcfdnU3L8'
if ($LASTEXITCODE -ne 0) { throw 'Saved snapshot retrieval/identity validation failed; stop' }
$cp6Hash = ($cp6HashOutput -join '').Trim()
if ($cp6Hash -notmatch '^[a-f0-9]{64}$') { throw 'No valid saved snapshot hash; stop' }

$cp6Authorization = [ordered]@{
    tenant_id = $cp6Tenant
    integration_id = $cp6Integration
    workflow_external_id = 'ievg2u7YcfdnU3L8'
    operation = 'retry_execution'
    idempotent = $true
    side_effect_safe = $true
    workflow_sha256 = $cp6Hash
}
$env:N8N_AUTHORIZATIONS = '[' + ($cp6Authorization | ConvertTo-Json -Compress) + ']'
```

The two safety declarations apply to the inspected two-node local-only demo, not the legacy order workflow. Review the saved execution snapshot, not just the workflow's current editor state. Do not edit/republish the demo between calibration and the real run. The full snapshot includes version-specific data; if a later execution's saved snapshot differs, the adapter must reject it rather than substituting a guessed hash.

## 4. Start the backend and verify ingestion before enabling dispatch

Run from the same controller so all children inherit the selected database, new signing secret, authorization, mode and queue. The API key remains loaded privately by Python Settings from `backend/.env`.

```powershell
$env:RECOVERY_MODE = 'real_n8n'
$cp6Temporal = Join-Path $cp6Backend '.temporal\cli\temporal.exe'
$cp6TemporalDb = Join-Path $cp6Backend ".temporal\cp6-temporal-$cp6Session.db"
$cp6TemporalProcess = Start-Process -FilePath $cp6Temporal -ArgumentList @('server','start-dev','--ip','127.0.0.1','--db-filename',('"' + $cp6TemporalDb + '"')) -WorkingDirectory $cp6Backend -WindowStyle Hidden -PassThru
$cp6ApiProcess = Start-Process -FilePath $cp6Python -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory $cp6Backend -WindowStyle Hidden -PassThru
$cp6FrontendProcess = Start-Process -FilePath 'cmd.exe' -ArgumentList @('/d','/c','npm.cmd run dev -- --host 127.0.0.1') -WorkingDirectory (Join-Path $cp6Root 'frontend') -WindowStyle Hidden -PassThru
```

Wait for `/health` and Temporal 7233 before proceeding. Do not launch a duplicate provider: the existing one was verified. If it has stopped, start it from this shell with:

```powershell
# Only if no process is listening on 8011:
$cp6ProviderProcess = Start-Process -FilePath $cp6Python -ArgumentList @('-m','uvicorn','scripts.n8n_demo_provider:app','--host','127.0.0.1','--port','8011') -WorkingDirectory $cp6Backend -WindowStyle Hidden -PassThru
```

The next commands trigger a **new** controlled failure for the real demonstration, but dispatch is still stopped. Use a new UUID; reusing calibration input would make the provider succeed immediately.

```powershell
$cp6ReadToken = [System.Net.NetworkCredential]::new('', (Read-Host 'New CP6 tenant read token (hidden)' -AsSecureString)).Password
$cp6ReadHeaders = @{ Authorization = 'Bearer ' + $cp6ReadToken }
$cp6Status = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/system/status' -Headers $cp6ReadHeaders
if ($cp6Status.tenant_id -ne $cp6Tenant -or $cp6Status.recovery_mode -ne 'real_n8n') { throw 'Wrong tenant/database/mode; stop' }

$cp6Run = [guid]::NewGuid().ToString()
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:5678/webhook/rebootx-safe-demo' -ContentType 'application/json' -Body (@{run_id=$cp6Run} | ConvertTo-Json)

# Wait for n8n's Error Workflow delivery to finish, then inspect this isolated tenant:
$cp6Incidents = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/incidents?limit=10' -Headers $cp6ReadHeaders
$cp6Candidates = @($cp6Incidents.items | Where-Object { $_.workflow_external_id -eq 'ievg2u7YcfdnU3L8' -and $_.status -eq 'RECEIVED' })
if ($cp6Candidates.Count -ne 1) { throw 'Expected exactly one signed, registered CP6 incident; keep dispatch stopped' }
$cp6Incident = $cp6Candidates[0]
$cp6Recovery = Invoke-RestMethod -Uri ("http://127.0.0.1:8000/api/v1/incidents/" + $cp6Incident.id + '/recovery') -Headers $cp6ReadHeaders
if ($cp6Recovery.mode -ne 'real_n8n') { throw 'Incident is not pinned to real mode; stop' }
```

Inspect the new original execution in n8n: match its Webhook `run_id` to `$cp6Run`, confirm the first local 503 and wait for handler success. This successful ingestion establishes that runtime integration UUID, actual workflow ID and signing secret agree with the newly selected backend. If ingestion fails, keep dispatch stopped; do not modify signatures or bypass authentication.

## 5. Explicit execution boundary: start recovery only when ready

**Do not run this section during configuration-only preparation.** These commands start the existing worker/dispatcher and cause the pending real action. Run only after the previous checks, retry permission review, saved-snapshot review and the operator's decision to perform the controlled demonstration.

```powershell
$cp6WorkerProcess = Start-Process -FilePath $cp6Python -ArgumentList @('-m','app.temporal.worker') -WorkingDirectory $cp6Backend -WindowStyle Hidden -PassThru
$cp6DispatcherProcess = Start-Process -FilePath $cp6Python -ArgumentList @('-m','app.temporal.dispatcher') -WorkingDirectory $cp6Backend -WindowStyle Hidden -PassThru

# Poll the known incident. No token or signature is printed.
$cp6Deadline = (Get-Date).AddMinutes(2)
do {
    $cp6Result = Invoke-RestMethod -Uri ("http://127.0.0.1:8000/api/v1/incidents/" + $cp6Incident.id + '/recovery') -Headers $cp6ReadHeaders
    if ($cp6Result.status -in @('RECOVERED','NEEDS_ATTENTION')) { break }
    Start-Sleep -Seconds 2
} while ((Get-Date) -lt $cp6Deadline)

[pscustomobject]@{
    Incident = $cp6Incident.id
    OriginalExecution = $cp6Incident.source_execution_id
    ResultingExecution = $cp6Result.external_execution_id
    Status = $cp6Result.status
    Verification = $cp6Result.verification_outcome
    FailureReason = $cp6Result.escalation_reason
}
if ($cp6Result.status -ne 'RECOVERED' -or $cp6Result.verification_outcome -ne 'REAL_RECOVERY_VERIFIED') { throw 'Real recovery is not verified; inspect redacted evidence, do not force a retry' }
```

Open `http://127.0.0.1:5173`, sign in with the new CP6 read token, and inspect the known incident's attempts, evidence and audit timeline. Independently inspect the resulting execution in n8n and confirm `success`, the same workflow ID and correct original retry linkage. The backend already requires this independent read, but retaining both views makes the live evidence reviewable.

Keep the controller/session environment private. To stop later, use the retained process handles for the CP6 processes only; do not use broad process-name termination. Keep the new demo database for evidence. No database deletion/reset or credentials-on-disk edit is part of these instructions.

## Inspection limits and unchanged state

All actual HTTP calls in this preflight were GETs. Database inspections used an explicit PostgreSQL READ ONLY transaction and SQLite `mode=ro`. No calibration, ingestion, retry, worker dispatch, n8n restart, API-key change, migration or registration was executed. Only this redacted report was added to source; an ignored `.temporal/cp6-preflight-command-review.json` file holds its non-secret command blocks for static PowerShell parsing (zero parse errors). Existing Git changes remain uncommitted; no commit/push was performed.

The historical [CP6 implementation report](CHECKPOINT6_REPORT.md) accurately records the earlier no-key blocker. This preflight supersedes that single configuration fact: a key now exists and authenticated reads work. Full Checkpoint 6 remains partially complete until an actual authorized action and independent verification succeed.
