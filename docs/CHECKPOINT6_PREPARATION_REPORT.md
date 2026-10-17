# Checkpoint 6 controlled demonstration: preparation report

Prepared October 17, 2026 (Asia/Calcutta). **Preparation completed; calibration awaits confirmation. Checkpoint 6 is not complete.**

No n8n restart, calibration trigger, FastAPI startup, Temporal server/worker/dispatcher startup, recovery dispatch or external recovery action occurred. Only reversible isolated setup and read-only integration checks were performed.

## Completed setup and checks

- `python -m scripts.provision --help` confirms `--workflow-kind` supports `side_effect_safe_demo_v1`.
- Existing n8n API-key authenticated GETs returned **200** for the actual workflow, execution list, and a separate metadata-only execution read. No API key or token was printed. Retry permission is not implied by these reads and remains a future live-action prerequisite.
- Workflow `ievg2u7YcfdnU3L8` is active, named `REBOOTX Side Effect Safe Recovery Demo`, with Error Workflow `wmtArUNSGBtEuCUM` selected. No workflow definitions or n8n internal database records were changed.
- The provider's GET `http://127.0.0.1:8011/openapi.json` returned **200**, with the expected title and `/probe/{run_id}` route. No probe POST was made.
- A fresh SQLite file was created under a unique ignored preparation directory. Before Alembic ran, a guard verified that Settings selected this exact new file, that it did not exist, and that the selected driver was SQLite. Neon was never selected by the migration/provisioning commands.
- Alembic upgraded the isolated database to **0004**. `alembic check` reported **No new upgrade operations detected**. Independent queries verified revision `0004` and all CP6 columns (`recovery_mode`, `external_action_key`, `evidence`).
- Existing `scripts.provision.main` registered the demo using its supported arguments and existing validation/ORM transaction. Its hidden token input was supplied from a newly generated process-local random token; neither token nor signing secret appeared in command arguments or output.
- Independent reads verified tenant/integration/workflow relationships, enabled flags and `side_effect_safe_demo_v1` kind.
- A generated session loader successfully decrypted the new Windows-protected demo credentials. Existing bearer authentication accepted the stored token, and existing webhook authentication accepted a correctly signed in-memory test body and rejected an invalid signature with 401. This was a helper-level authentication check, not an HTTP event submission; no incident was created.

## Actual isolated database and IDs

Preparation directory:

```text
C:\Users\Saksham\OneDrive\Desktop\Rebootx-ai\backend\.temporal\cp6-prep-7163e9b9ff1143aeaa6e72939962467f
```

| Field | Actual value |
| --- | --- |
| Database | `demo.db` inside the preparation directory |
| Migration | `0004` |
| Tenant name | `CP6 Safe Demo` |
| Tenant ID | `0610d06e-460f-465e-8b19-f80b336fd8e7` |
| Integration ID | `38979968-2d1f-4fd0-9307-c829e54ba58f` |
| Internal workflow registration ID | `29a98f88-14f2-4ca3-822e-4e760cc05756` |
| Actual n8n workflow ID | `ievg2u7YcfdnU3L8` |
| Workflow kind | `side_effect_safe_demo_v1` |
| Signing secret reference | `CP6_DEMO_WEBHOOK_SECRET` |
| Prepared Temporal queue | `rebootx-cp6-7163e9b9ff1143aeaa6e72939962467f` |
| Recovery mode | `mock-only` |
| N8N authorizations | Empty array |
| Incidents / outbox / attempts | `0 / 0 / 0` |

These IDs came from the actual committed isolated registration; none were guessed. There are no pending actions for automatic dispatch.

## Signing configuration and protected credentials

The preparation directory contains:

- `manifest.json`: non-secret database path, registration IDs, queue and explicit inactive recovery settings.
- `secrets.dpapi`: **encrypted** new demo signing secret and new tenant read token, protected by Windows DPAPI for this Windows account. It does not contain the existing n8n API key. No plaintext secret file was created.
- `load-session.ps1`: loads the private session environment only; it contains no credential literals and starts no services.

All these files are ignored by the existing `backend/.temporal/` Git rule. DPAPI reload was verified. Keep the directory private and use the same Windows account/machine for decryption. Do not print the process environment, decoded credential object, or read token.

The loader stages:

```text
REBOOTX_BASE_URL=http://127.0.0.1:8000
REBOOTX_INTEGRATION_ID=38979968-2d1f-4fd0-9307-c829e54ba58f
REBOOTX_WORKFLOW_EXTERNAL_ID=ievg2u7YcfdnU3L8
REBOOTX_WEBHOOK_SECRET=<loaded privately from Windows-protected storage>
CP6_DEMO_WEBHOOK_SECRET=<same private signing secret, resolved by backend registration>
CP6_DEMO_READ_TOKEN=<loaded privately; never printed>
```

**The currently running n8n process has not received this staged environment.** Its live signing configuration is not yet verified. The existing Error Handler resolves `$vars` before process environment; the previous preflight's variables API returned 403, so variable overrides remain unverified. A restart with the staged environment and a controlled calibration/ingestion check require the user's confirmation. Enabling n8n Code-node environment access is also a deliberate part of that future demo-session startup; it was not changed in the running service during preparation.

## Preservation and runtime selection

The preparation script compared SHA-256 hashes before/after setup and confirmed that both `backend/.env` and `.temporal/live_demo.db` were unchanged. Existing credentials were not rotated or edited. No connection to Neon was used by setup. The previously inspected Neon and historical SQLite databases remain outside this prepared target; their migrations were not applied or revalidated in this task.

**`backend/.env` still selects its existing Neon database.** The isolated target is selected by the prepared session's environment, not by editing `.env` or permanently changing Windows environment settings. Every future backend child must inherit the prepared session; do not launch the API/worker/dispatcher from an unrelated shell with default settings.

To restore the prepared environment later, the following command is safe by itself: it loads secrets privately and keeps mode `mock-only`, authorizations empty and all services stopped. It does not restart n8n or trigger anything. Script text is executed directly to accommodate the existing PowerShell script policy without changing that policy.

```powershell
$cp6Prep = 'C:\Users\Saksham\OneDrive\Desktop\Rebootx-ai\backend\.temporal\cp6-prep-7163e9b9ff1143aeaa6e72939962467f'
$cp6Load = Join-Path $cp6Prep 'load-session.ps1'
& ([scriptblock]::Create((Get-Content -LiteralPath $cp6Load -Raw))) -PreparationDirectory $cp6Prep
```

This loader was executed successfully in a private verification process. That process has exited; the encrypted files retain the prepared credentials for future authorized use. Do not rerun `prepare_cp6_demo.ps1` to resume: it deliberately creates a separate fresh preparation on every invocation.

## Snapshot calibration and N8N_AUTHORIZATIONS readiness

The workflow still has no saved demo executions in the read-only API response. No calibration was triggered. Consequently:

- `calibration_execution_id` is null.
- `workflow_sha256` is null.
- `N8N_AUTHORIZATIONS` deliberately remains `[]`; no placeholder/dummy hash was inserted.
- The known authorization values are the actual tenant/integration IDs above, external workflow `ievg2u7YcfdnU3L8`, and supported operation `retry_execution`.
- Future `idempotent=true` / `side_effect_safe=true` declarations are limited to the reviewed local-only two-node demo. They are not activated yet.
- Existing `Settings`/`N8nAuthorization` schema was inspected. The only missing live-derived authorization value is the exact saved failed execution's `workflowData` SHA-256. Retry permission/project execution access and runtime signing still need verification before any real action.

After confirmation, the planned calibration sequence is:

1. Establish that this local n8n instance can be used as a dedicated demo session and that other workflows will not rely on the shared Error Handler while its process environment targets the new CP6 integration. Do not change production workflow definitions or overwrite existing credentials.
2. Load the prepared environment, stop/restart the existing local n8n instance with the dedicated signing configuration, and verify the actual imported workflow ID is still `ievg2u7YcfdnU3L8`. Resolve `$vars` overrides explicitly if present.
3. Keep FastAPI, Temporal worker and dispatcher stopped. Check the provider remains available.
4. Submit **one** controlled calibration webhook with a fresh run UUID, after the user confirms this trigger. It must fail at the local provider's first 503. With FastAPI stopped, the Error Handler delivery cannot queue recovery. Wait for that delivery attempt to finish; do not redeliver it.
5. Read the actual failed execution, correlate its original Webhook body run UUID, validate its workflow ID/error status/retry linkage and review its saved safe graph. Derive the hash with the existing read-only fingerprint script.
6. Build authorization only from those actual values. Keep dispatch disabled; enabling real mode or starting recovery services requires a separate user decision.

The exact existing fingerprint command, **after the actual calibration execution ID exists**, is:

```powershell
# In the private loaded preparation shell, after calibration is authorized and completed:
$cp6ExecutionId = Read-Host 'Actual failed calibration execution ID'
if ($cp6ExecutionId -notmatch '^[1-9][0-9]{0,19}$') { throw 'Invalid execution ID' }
.venv\Scripts\python.exe -B -m scripts.n8n_fingerprint --execution-id $cp6ExecutionId --workflow-id 'ievg2u7YcfdnU3L8'
```

No current workflow GET hash or guessed execution ID can replace this saved-execution hash.

## Remaining blockers and exact next action

**Next action: ask for confirmation to restart the existing local n8n instance with the prepared dedicated signing configuration and run one controlled calibration failure, while FastAPI/worker/dispatcher remain stopped.** This confirmation is required by the user's explicit execution boundary. The restart must also be suitable for the shared Error Handler's other users; no production workflow changes are proposed.

Until then, leave everything staged. Real retry permission remains unproven by read-only checks, and no real recovery success can be claimed. Starting any recovery services or dispatch requires separate explicit authorization; this preparation does not grant it.

## Files and validation

Added source files:

- `backend/scripts/prepare_cp6_demo.ps1`: isolated-only preparation utility; no service-start, restart or HTTP mutation logic.
- `docs/CHECKPOINT6_PREPARATION_REPORT.md`: this redacted report.

Generated local artifacts are confined to the unique ignored preparation directory above. PowerShell source parsing, real isolated migration/provisioning, model-drift check, protected-credential reload, scoped registration reads and existing authentication helper checks passed. No full regression suite was rerun because application Python code was not changed. Existing user work was preserved; no commit or push was performed.
