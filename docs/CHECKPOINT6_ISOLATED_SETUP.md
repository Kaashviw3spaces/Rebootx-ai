# Checkpoint 6 isolated n8n setup status

October 17, 2026 (Asia/Calcutta). **Isolated server started; owner/key initialization requires user action. No calibration or recovery performed.**

## 1. Startup

- Origin: `http://127.0.0.1:5680`, listening on loopback only.
- Internal JavaScript runner broker: `127.0.0.1:5681`; JavaScript runner registration appears in the local startup log.
- Native n8n 2.43.6 was launched hidden using the existing cached binary. No download or system configuration change was required.
- GET `/healthz` and GET `/` returned HTTP 200.
- Recorded n8n process ID at startup: `11612` (use the saved instance manifest when resuming; verify live identity before any future process operation).

## 2. Database and encryption isolation

Dedicated working/user directory:

```text
C:\Users\Saksham\OneDrive\Desktop\Rebootx-ai\backend\.temporal\cp6-prep-7163e9b9ff1143aeaa6e72939962467f\n8n-isolated-cf55be3ca4c14ec192554c8fc17c05fe
```

n8n created its own `.n8n/database.sqlite` and `.n8n/config` beneath this directory. The new config contains an automatically generated encryption key; the value was never printed. No shared database, key or credentials were copied. The new working directory has no `.env` file.

The child environment was constructed from an allowlist, with explicit `N8N_USER_FOLDER`, absolute `DB_SQLITE_DATABASE`, `DB_TYPE=sqlite`, HTTP 5680 and broker 5681. It did not inherit a shared database URL, API key, encryption key or backend read token. The only demo secret passed to it was the separately staged CP6 signing secret. This environment is retained encrypted with Windows DPAPI in `process-environment.dpapi`, within the ignored isolated directory.

Read-only inspection of the new database found zero workflows, zero executions and zero workflow variables. No existing historical SQLite or Neon database was modified.

## 3. Workflow IDs and import status

Import is **pending owner initialization**. No workflows have been imported yet, so actual imported IDs cannot yet be reported or verified.

A two-workflow import copy is prepared as `cp6-workflows.json` in the isolated directory. It uses only the repository's reviewed Error Handler and local-only safe demo, has no node credential references, and explicitly supplies:

| Workflow | Expected preserved ID |
| --- | --- |
| Side Effect Safe Recovery Demo | `ievg2u7YcfdnU3L8` |
| CP6 Error Handler | `wmtArUNSGBtEuCUM` |

The copy sets `demo.settings.errorWorkflow` to `wmtArUNSGBtEuCUM`. Both copies are inactive. No shared workflow was exported with credentials or modified. The installed supported CLI importer retains supplied IDs; the prepared import helper checks the exact resulting IDs and stops if either differs. It also refuses to overwrite an existing workflow or proceed if executions already exist.

## 4. Error Handler assignment

The intended assignment is already set in the isolated import copy. Actual persisted assignment remains **pending import**. The shared instance's assignments were left unchanged.

## 5. API authentication

The new isolated instance needs its own owner account and API key. The old shared key was not copied. Owner initialization and encrypted new-key storage were still absent at the last check, so authenticated isolated API reads have **not** been verified.

User action:

1. Open `http://127.0.0.1:5680` in a private browser window, to avoid mixing login cookies with the shared instance.
2. Initialize the isolated instance's owner account using the UI. Do not reuse/export shared instance credentials.
3. Under Settings -> n8n API, create a new key for this isolated instance. If scope selection is available, include workflow list/read and execution list/read/retry; activation access will be needed before a later approved calibration. Do not publish or trigger anything yet.
4. Save the key privately using this hidden-entry command in PowerShell. Never paste it into chat:

```powershell
$cp6Prep = 'C:\Users\Saksham\OneDrive\Desktop\Rebootx-ai\backend\.temporal\cp6-prep-7163e9b9ff1143aeaa6e72939962467f'
$cp6Save = 'C:\Users\Saksham\OneDrive\Desktop\Rebootx-ai\backend\scripts\save_cp6_isolated_api_key.ps1'
& ([scriptblock]::Create((Get-Content -LiteralPath $cp6Save -Raw))) -PreparationDirectory $cp6Prep
```

The prompt uses `Read-Host -AsSecureString`, writes only DPAPI ciphertext to the isolated `api-key.dpapi` file, refuses to replace an existing saved key, and does not edit `backend/.env`.

## 6. Signing configuration

The isolated process was started with the prepared integration UUID `38979968-2d1f-4fd0-9307-c829e54ba58f`, actual demo workflow ID `ievg2u7YcfdnU3L8`, backend destination `http://127.0.0.1:8000`, and the staged secret. Private comparisons verified that the staged signing secret and both IDs match the existing CP6 preparation. The secret was never printed.

Code-node environment access is enabled only in the new isolated process, whose sensitive environment is deliberately limited. The new database has no `$vars` overrides. Runtime signing through an actual Error Trigger has not been tested because workflows must not be triggered during this setup.

## 7. Backend compatibility and inactive recovery

Existing backend preparation is retained:

- Tenant: `0610d06e-460f-465e-8b19-f80b336fd8e7`
- Integration: `38979968-2d1f-4fd0-9307-c829e54ba58f`
- Internal workflow: `29a98f88-14f2-4ca3-822e-4e760cc05756`
- Expected external ID: `ievg2u7YcfdnU3L8`
- Kind: `side_effect_safe_demo_v1`
- Isolated CP6 backend SQLite revision: `0004` (established during preparation).

Compatibility will be confirmed against the actual n8n import IDs before proceeding. No backend registration has been silently changed.

`load_cp6_isolated_backend.ps1` is ready to load the existing prepared backend database/secret plus `N8N_BASE_URL=http://127.0.0.1:5680` and the separately encrypted new API key. It refuses to run if that key has not been saved. It retains `RECOVERY_MODE=mock-only` and `N8N_AUTHORIZATIONS=[]` and starts no services. `backend/.env` remains unchanged; the new origin/key are session-only overrides.

## 8. Remaining blockers and planned completion

Owner initialization and private key entry require the user's local interaction. Once complete:

1. Use the supported CLI import helper against the isolated database only.
2. Verify exactly two actual workflow IDs and the Error Handler assignment; stop if IDs differ.
3. Load the isolated backend session and verify new-key workflow/execution reads against port 5680.
4. Confirm signing/registration consistency, no executions, and unchanged shared instance configuration.
5. Finish this setup without starting recovery services or triggering calibration.

Imports remain inactive. A later calibration stage will require publishing only the isolated demo/handler, verifying that API/signing configuration is ready, and explicit authorization for one controlled trigger. The snapshot hash remains unavailable until that future failed execution exists; no dummy authorization is enabled.

## 9. Preserved shared instance and other restrictions

Read-only checks after isolated startup confirmed that port 5678 remained reachable, the same four shared workflows remained active, and the Primary Order Notification Dispatcher's handler remained `jfUNuHPdxg4WXlg9`. No shared workflow or credential settings were changed, and the shared process was not restarted or stopped.

FastAPI 8000 and Temporal 7233 were closed during checks. No recovery worker or outbox dispatcher was launched. No workflow was triggered, no execution retried, no internal n8n database was edited directly, and no commit/push occurred. New n8n initialization writes were performed solely by the supported native n8n service within its own new database.

Added setup helpers: `start_cp6_isolated_n8n.ps1`, `save_cp6_isolated_api_key.ps1`, `load_cp6_isolated_backend.ps1`, `import_cp6_isolated_workflows.ps1`. Their PowerShell syntax is checked; startup and credential-isolation checks ran. The import and authenticated-read steps await the user-owned prerequisites. Generated state, encrypted files, logs and import copies are beneath the existing ignored `.temporal/` path.
