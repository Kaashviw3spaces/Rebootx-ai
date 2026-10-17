    # Checkpoint 6: controlled Windows demonstration

    Status on October 17, 2026: **live n8n recovery blocked: no public API key configured**. The user confirmed this blocker. The commands below are a reproduction guide, not evidence that a real recovery ran.

    ## Supported boundary

    The locally installed npm-cache package is n8n **2.43.6**. Its bundled `dist/public-api/v1/openapi.yml` and `controllers/executions.public.controller.js` document and implement:

    - `GET /api/v1/executions/{executionId}`: inspect identity, saved workflow, status and retry linkage.
    - `POST /api/v1/executions/{executionId}/retry`, body `{"loadWorkflow":false}`: retry the saved execution workflow and return a new execution ID.
    - A separate GET of the resulting execution is required to verify success.

    Authentication uses `X-N8N-API-KEY`. Grant `execution:read` and `execution:retry`, plus workflow execution access in the intended n8n project. Restrict the key to the demo project where available. Do not use editor session cookies, `/rest` endpoints, n8n database writes, or an invented generic workflow-run API. n8n Webhook nodes provide the supported initial production trigger. No generic arbitrary-workflow execution adapter is implemented.

    Official background: [API authentication](https://docs.n8n.io/api/authentication/), [API reference](https://docs.n8n.io/api/api-reference/), [failed execution retries](https://docs.n8n.io/workflows/executions/all-executions/). Installed package files take precedence over current online documentation for this implementation. Other n8n versions require a fresh compatibility audit.

    ## Configuration

    Existing Pydantic settings use these environment names (no `REBOOTX_` prefix). Defaults are safe: `RECOVERY_MODE=mock-only`, empty credentials, empty authorization list, and no supported-version opt-in. Settings must be consistent in API, worker, and dispatcher shells. Never place credentials in `VITE_*`, workflow JSON, source control, command arguments, or reports. Use a server secret store or an interactive hidden prompt; this guide does not edit `backend/.env`.

    | Variable | Meaning |
    | --- | --- |
    | `RECOVERY_MODE` | `mock-only` or explicitly `real_n8n`; pinned on incident ingestion |
    | `N8N_BASE_URL` | Origin only, default `http://127.0.0.1:5678`; HTTPS required outside loopback |
    | `N8N_API_KEY` | Server-only n8n public API credential, represented as `SecretStr` |
    | `N8N_SUPPORTED_VERSION` | Must explicitly be `2.43.6`; operator attestation, not automatic remote version discovery |
    | `N8N_AUTHORIZATIONS` | JSON array binding tenant UUID, integration UUID, actual n8n workflow ID, operation and snapshot hash |
    | `N8N_CONNECT_TIMEOUT` | Default 2 seconds, configurable 0.1–5 |
    | `N8N_READ_TIMEOUT` | Default 5 seconds, configurable 0.1–10 |
    | `N8N_VERIFICATION_SECONDS` | Default 15, maximum 20; additionally limited to 20 polls with up to 0.5-second sleeps |

    Authorization entry, with placeholders replaced only after reviewing the demo snapshot:

    ```json
    [{"tenant_id":"<tenant UUID>","integration_id":"<integration UUID>","workflow_external_id":"<actual n8n workflow ID>","operation":"retry_execution","idempotent":true,"side_effect_safe":true,"workflow_sha256":"<64 lowercase hex characters>"}]
    ```

    Both boolean safety declarations default to false. The registered workflow must have kind `side_effect_safe_demo_v1`. Notification/customer/payment workflows are ineligible for this initial adapter. The snapshot hash is over the full saved `workflowData` object using sorted compact UTF-8 JSON, including node code and credential references. Operator review and the explicit safety declaration are required; REBOOTX cannot prove arbitrary workflow code is harmless. The hash is checked against the original failed execution immediately before retry. `loadWorkflow=false` prevents silently switching to an edited workflow. Reauthorize changed snapshots explicitly.

    ## Native services and demo preparation

    Use separate PowerShell terminals. Never reset a database. Applying migration `0004` to an existing database requires explicit operator approval and a backup; no live migration was performed during this task. Prefer a fresh, explicitly named disposable local demo database for the first real run. If using an existing database, obtain approval before registration or other record changes.

    From `backend/`, inspect migration status and, **only after approving the target database**, apply the additive migration:

    ```powershell
    .venv\Scripts\python.exe -m alembic current
    # Operator-approved target only:
    .venv\Scripts\python.exe -m alembic upgrade head
    ```

    Start the isolated in-memory provider; it only counts run UUIDs in memory, returns 503 once per UUID, then succeeds. It makes no external calls. Keep one provider process running throughout the demo.

    ```powershell
    .venv\Scripts\python.exe -m uvicorn scripts.n8n_demo_provider:app --host 127.0.0.1 --port 8011
    ```

    In n8n:

    1. Import `integrations/n8n/workflows/side_effect_safe_recovery_demo.json`. Its only action is a POST to the loopback provider. Review both nodes. Keep node-level automatic retries disabled.
    2. Import/reuse the existing REBOOTX Error Trigger workflow. Set the demo workflow's Error Workflow using n8n's workflow settings selector. Never select the existing order-notification workflow for this test.
    3. Obtain the actual n8n workflow ID and configure `REBOOTX_WORKFLOW_EXTERNAL_ID` in the error handler to that ID, rather than the legacy `notify-orders` alias. Configure its integration UUID, dedicated webhook signing secret, and REBOOTX URL as described in `integrations/n8n/README.md`. Keep secrets out of exported workflows. On native n8n, environment access must be configured before startup if used by the Code node.
    4. Save/publish the demo workflow. Use its production `/webhook/` URL; manual editor runs do not reliably trigger Error Trigger workflows.

    Provision a dedicated tenant/integration/workflow on the approved disposable database. `DEMO_N8N_WEBHOOK_SECRET` must already hold a dedicated signing secret (minimum 32 characters). The tenant read token is entered using a hidden prompt.

    ```powershell
    .venv\Scripts\python.exe -m scripts.provision --tenant-name "CP6 Safe Demo" --workflow-external-id "<actual n8n workflow ID>" --workflow-kind side_effect_safe_demo_v1 --secret-env DEMO_N8N_WEBHOOK_SECRET
    ```

    ## Review and pin the saved snapshot

    Before starting the recovery worker/dispatcher, run a **calibration failure** to capture the saved workflow snapshot. Do not queue recovery for that calibration run: keep FastAPI stopped until the handler's failed delivery finishes, and do not manually redeliver it later. Run the local provider and n8n only. Use a fresh UUID for each demonstration or calibration.

    ```powershell
    $runId = [guid]::NewGuid().ToString()
    Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5678/webhook/rebootx-safe-demo -ContentType application/json -Body (@{run_id=$runId} | ConvertTo-Json)
    ```

    Inspect n8n's failed execution and both demo nodes. Configure the public API key securely in the server environment. Then use this read-only command from `backend/` to calculate the hash; it prints only the hash, never the execution payload or key:

    ```powershell
    $env:N8N_BASE_URL = 'http://127.0.0.1:5678'
    $env:N8N_SUPPORTED_VERSION = '2.43.6'
    .venv\Scripts\python.exe -m scripts.n8n_fingerprint --execution-id "<calibration execution ID>" --workflow-id "<actual n8n workflow ID>"
    ```

    Set `N8N_AUTHORIZATIONS` using the reviewed hash and registered IDs. Set `RECOVERY_MODE=real_n8n` in the FastAPI and worker environments before starting them. Select `AI_PROVIDER=gemma` for the existing deterministic HTTP-503 fast path, or use `mock` for explicitly simulated advisory diagnosis; recovery provenance is independent of diagnosis provenance. A mock diagnosis never authorizes the action by itself.

    Start native n8n (if not already running) with its error-handler environment configured. Using the already installed version avoids silently fetching a different release:

    ```powershell
    node.exe "$env:LOCALAPPDATA\npm-cache\_npx\a8a7eec953f1f314\node_modules\n8n\bin\n8n" start
    ```

    Start the remaining services from `backend/`, one per terminal with the same approved database and recovery configuration:

    ```powershell
    .temporal\cli\temporal.exe server start-dev --ip 127.0.0.1 --db-filename .temporal/rebootx-server.db
    .venv\Scripts\python.exe -m app.temporal.worker
    .venv\Scripts\python.exe -m app.temporal.dispatcher
    .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
    ```

    From `frontend/`:

    ```powershell
    npm.cmd run dev -- --host 127.0.0.1
    ```

    Send the production webhook request again with a **new** UUID. The local provider fails once; n8n's Error Trigger signs a real event; REBOOTX ingests, diagnoses and gates it; Temporal reserves a retry and calls the public API; REBOOTX independently reads the resulting execution. Log into the dashboard with the tenant read token and open the new incident.

    Capture only redacted evidence: original execution ID, resulting execution ID, `retry_execution`, `REAL_RECOVERY_VERIFIED`, `RECOVERED`, action/verification timestamps, and the tenant-scoped timeline. Obtain evidence from n8n, `/api/v1/incidents/{id}/recovery`, `/attempts`, and `/timeline`. Success requires the resulting execution's `workflowId` and `retryOf` to match and its independently read terminal status to be `success`. HTTP 200 from the retry endpoint is insufficient.

    ## Failure handling and limitations

    - Missing credentials, unsupported version/method, wrong workflow/snapshot, missing scope, expired executions, payment/non-demo kinds, non-idempotent declarations, authentication/payload errors, and unsafe policy decisions fail closed.
    - Retry chains (`retryOf` present) and original executions with a known successful retry are rejected. This limits recovery loops if retries themselves trigger error handlers.
    - One durable reservation is shared across incidents for the same tenant/integration/original execution, even if different failed steps are reported. It is not an n8n exactly-once guarantee.
    - No POST is automatically retried, including after 429/500/503 or transport timeout. Temporal activity redelivery reuses the committed result or escalates an uncertain reservation. A crash before the POST may conservatively leave an unused reservation.
    - Verification polls are bounded; running/waiting/unknown status, read errors, missing linkage or deadline expiry become `REAL_RECOVERY_UNVERIFIED` and `NEEDS_ATTENTION`. Terminal error/canceled/crashed becomes `REAL_RECOVERY_FAILED`.
    - No automatic reconciliation/retry of uncertain actions or later-completing executions is implemented. Operators must inspect n8n; do not clear reservations to force another action.
    - Only the inspected 2.43.6 interface is enabled. No live n8n key was available during implementation; authentication, runtime snapshot stability, and end-to-end execution still need live validation.
    - Native Temporal tests use disposable SQLite persistence and mocked n8n HTTP. They demonstrate orchestration/retry/replay behavior, not a successful live n8n recovery.

    Troubleshooting: verify actual workflow ID rather than its display name/legacy alias; confirm the Error Workflow selection and production trigger; check separate signing/API credentials; use the same mode/database settings in API and worker; review fixed failure codes in the timeline. Changed snapshots require a new review/hash. Oversized/redacted/missing snapshots fail closed. Do not print raw HTTP bodies or credentials while debugging.
