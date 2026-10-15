# REBOOTX — n8n Automation Failure Ingestion & Recovery

This directory contains the production-ready n8n integration assets for REBOOTX. It connects customer n8n workflow failures to REBOOTX's durable recovery platform via HMAC-authenticated webhooks and Temporal orchestration.

---

## 1. Architecture Overview

```text
Customer n8n Instance
  ├─ Primary Workflow (e.g. Order Confirmation)
  │    └─ Primary Notification Node (fails with HTTP 503 / timeout)
  │
  └─ REBOOTX Error Handler Workflow (configured as Error Workflow)
       ├─ Error Trigger: intercepts execution failure context
       ├─ Format & Sign (Code node):
       │    ├─ maps to strict FailureEvent schema
       │    ├─ derives stable event_id and operation_id (no random/Date.now tokens)
       │    └─ computes exact-byte HMAC-SHA256 signature
       └─ HTTP Request: POSTs to /api/v1/events/failure

REBOOTX Platform
  ├─ FastAPI Ingestion: validates exact-byte HMAC and timestamp (+/- 300s)
  ├─ Atomic Persistence: Incident (RECEIVED) + AuditLog + RecoveryOutbox
  ├─ Transactional Outbox Dispatcher: claims due rows with 60s lease
  ├─ Temporal Worker: IncidentRecoveryWorkflow
  │    ├─ VALIDATING -> DIAGNOSING (Gemma 4 / fast-path)
  │    ├─ PLANNED -> EXECUTING (bounded mock retry/fallback)
  │    └─ VERIFYING -> RECOVERED / NEEDS_ATTENTION
  └─ Read API: authorized recovery and audit timeline inspection
```

---

## 2. Workflows Included

1. **`workflows/primary_order_notification.json`**:
   - Represents a production order processing automation.
   - Nodes:
     - `Manual Trigger`: Manual test trigger.
     - `Create Synthetic Order`: Generates sample order item with `order_id`, `customer_email`, `operation_id = "notify-order-1042"`, `amount`.
     - `Send Customer Confirmation`: Attempts an HTTP request to `http://127.0.0.1:8000/mock/primary-provider-failure` which returns a simulated `503 Service Unavailable`.
   - Settings:
     - `executionOrder`: `v1`
     - `errorWorkflow`: `REBOOTX Error Handler`

2. **`workflows/rebootx_error_handler.json`**:
   - Generic failure ingestion handler.
   - Nodes:
     - `Error Trigger`: Captures failed execution context (`execution.id`, `lastNodeExecuted`, `error.message`, etc.).
     - `Format & Sign Failure Event`: Code node embedding `code_nodes/format_and_sign_failure.js`.
     - `Send to REBOOTX Ingestion`: HTTP Request node sending raw JSON with `X-Integration-ID` and `X-Webhook-Signature`.

3. **`code_nodes/format_and_sign_failure.js`**:
   - Reusable, stand-alone JavaScript mapping and signing utility.
   - **Native & Sandbox Safe**: Uses Node.js `crypto` if available; if n8n sandbox policy restricts `require('crypto')` (`NODE_FUNCTION_ALLOW_BUILTIN` unset), it transparently falls back to an embedded zero-dependency FIPS 180-4 pure JS HMAC-SHA256 implementation.
   - **Stable Deduplication**: Generates `event_id = "n8n:<exec_id>:<failed_step>"`, ensuring retries of the same failure do not create duplicate incidents or redundant workflows.

---

## 3. Docker-Free Local Setup on Windows

### Prerequisites
- Node.js 18+ installed on Windows.
- Python 3.11+ virtual environment configured in `backend/`.

### Step 1: Start n8n Natively on Windows
Run n8n in a PowerShell terminal (zero Docker / zero WSL):
```powershell
npx.cmd n8n
```
*(By default, n8n opens in your browser at `http://localhost:5678`).*

### Step 2: Configure Environment Variables in n8n
Configure the REBOOTX credentials and allow the Code node to access them:
```powershell
$env:N8N_BLOCK_ENV_ACCESS_IN_NODE = "false"
$env:REBOOTX_BASE_URL = "http://127.0.0.1:8000"
$env:REBOOTX_INTEGRATION_ID = "<YOUR_INTEGRATION_UUID>"
$env:REBOOTX_WEBHOOK_SECRET = "<YOUR_INTEGRATION_SECRET>"
$env:REBOOTX_WORKFLOW_EXTERNAL_ID = "notify-orders"
npx.cmd n8n start
```
*Note: In n8n, Error Trigger workflows execute when an active workflow fails during production runs (e.g. triggered via Webhook or Schedule, rather than manual execution inside the canvas). Ensure both workflows are published/active.*

### Step 3: Provision Tenant and Integration in REBOOTX
From the `backend/` directory:
```powershell
.venv\Scripts\python -m scripts.provision --tenant-name "Acme Demo Store" --workflow-external-id notify-orders --secret-env N8N_WEBHOOK_SECRET
```
- Note down the printed `Integration ID` and save your private `Tenant Read Token`.
- Ensure `N8N_WEBHOOK_SECRET` is set in `backend/.env` (minimum 32 characters).

### Step 4: Import Workflows into n8n
1. Open n8n at `http://localhost:5678`.
2. Go to **Workflows** -> **Import from File...**:
   - Import `integrations/n8n/workflows/rebootx_error_handler.json`.
   - Save the workflow as `REBOOTX Error Handler`.
3. In the `Format & Sign Failure Event` node, review the config or set `REBOOTX_INTEGRATION_ID` and `REBOOTX_WEBHOOK_SECRET` in the Code node or n8n variables.
4. Import `integrations/n8n/workflows/primary_order_notification.json`.
   - In **Workflow Settings**, confirm that **Error Workflow** is set to `REBOOTX Error Handler`.
   - Save the workflow.

---

## 4. Demonstrating End-to-End Failure Recovery

1. **Start REBOOTX Services** (in separate PowerShell terminals from `backend/`):
   ```powershell
   # Terminal 1: Native Temporal Server
   .temporal\cli\temporal.exe server start-dev --ip 127.0.0.1 --db-filename .temporal/rebootx-server.db

   # Terminal 2: Temporal Activity Worker
   .venv\Scripts\python -m app.temporal.worker

   # Terminal 3: Outbox Dispatcher
   .venv\Scripts\python -m app.temporal.dispatcher

   # Terminal 4: FastAPI Ingestion API
   .venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

2. **Trigger Failure in n8n**:
   - Open `Primary Order Notification Dispatcher` in n8n.
   - Click **Test step** or **Execute Workflow**.
   - Node `Send Customer Confirmation` calls `http://127.0.0.1:8000/mock/primary-provider-failure` and receives `HTTP 503`.
   - The workflow halts with an error, triggering `REBOOTX Error Handler`.
   - The error handler formats the failure, computes the HMAC-SHA256 signature, and POSTs to `/api/v1/events/failure`.

3. **Observe Ingestion & Recovery**:
   - In the API terminal, observe `POST /api/v1/events/failure 202 Accepted`.
   - In the Dispatcher terminal, observe `recovery_dispatched`.
   - In the Worker terminal, observe Temporal activities executing: `accept` -> `diagnose` -> `plan` -> `retry` -> `fallback` -> `verify` -> `recover`.

4. **Query Incident Status via Tenant Read Token**:
   ```powershell
   $readToken = "<YOUR_TENANT_READ_TOKEN>"
   $incidentId = "<INCIDENT_UUID>"
   Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/incidents/$incidentId/recovery" -Headers @{Authorization = "Bearer $readToken"}
   ```
   Output:
   ```json
   {
     "incident_id": "<INCIDENT_UUID>",
     "status": "RECOVERED",
     "verification_outcome": "MOCK_VERIFIED",
     "temporal_workflow_id": "rebootx:recovery:v1:<TENANT_UUID>:<INCIDENT_UUID>",
     "dispatch_status": "DISPATCHED",
     "diagnosis": {
       "status": "SUCCEEDED",
       "failure_category": "SERVICE_UNAVAILABLE",
       "provider": "deterministic",
       "recommended_action": "RETRY_WITH_BACKOFF"
     }
   }
   ```

5. **Verify Idempotency**:
   Re-running the error workflow for the same failed execution returns `duplicate: true`, keeping the existing incident record and preventing duplicate Temporal runs.

---

## 5. Security & Isolation Invariants

- **Exact-Byte HMAC:** Signatures are computed over the raw serialized JSON string. Any whitespace or key modification in transit invalidates the signature (`401 Unauthorized`).
- **Secret Safety:** The webhook secret is never sent over the wire and is never stored in the database.
- **Redaction:** Free-form error messages are redacted to `[REDACTED]` prior to persistence; only allowlisted numeric HTTP status codes and category enums are retained for diagnosis.
- **Tenant Scope:** Webhook authentication binds the incident strictly to the tenant owning the integration; callers cannot specify or forge tenant IDs.

