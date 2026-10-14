# Checkpoint 3 backend: advisory Gemma diagnosis and durable mock recovery

Python 3.11+; FastAPI, SQLAlchemy 2.x, PostgreSQL, Pydantic v2, Alembic, pytest, Google Gen AI SDK. Incidents are durably queued for Temporal. Diagnosis can use hosted Gemma; execution, fallback actions, and verification remain mock-only. It never sends notifications or invokes real automation adapters.

## Checkpoint 3: Gemma diagnosis

### Current Neon development validation (October 14)

Ownership/TLS/configuration and the Checkpoint 2 schema baseline were verified before applying only additive migration **0003** to the existing development database (**0002 -> 0003**). Final schema/model/constraint checks passed. PostgreSQL regression/persistence tests: **157 passed, 5 skipped** in isolated schemas; SQLite: **157 passed, 5 skipped**; native Temporal: **5 passed** separately with local SQLite and mocked model responses. Deterministic/Gemma/mock provenance, tenant isolation and linked recovery/audit/outbox records were verified. No live Gemma call was made during database validation.

All seven existing application tables were empty, and their counts/content hashes remained unchanged. Nonempty synthetic historical preservation was tested in isolated PostgreSQL schemas. Final public diagnosis count is zero; no test schemas remain. Actual `.env` and `AI_PROVIDER=mock` were unchanged. No historical migrations, existing user records, billing settings, commits or pushes were changed. See `IMPLEMENTATION.md` for evidence and limitations. Older database-unverified statements below describe prior sessions and are superseded by this development validation.

### Current live verification (October 14)

One actual production request for ambiguous synthetic HTTP 200/unknown-failure evidence bypassed the deterministic classifier and returned from `gemma-4-26b-a4b-it` in **21.622 seconds**. One candidate finished with `STOP`; its **347-character** response parsed as JSON and validated all seven required fields without repair. Gemma recommended `UNKNOWN_ERROR` / `ESCALATE` at confidence `0.1`. The deterministic policy required human approval, safely denying recovery (`AI_HUMAN_APPROVAL_REQUIRED`). Validating that denial satisfies the diagnosis/policy gate; it does not imply an external recovery succeeded.

The request used the existing production prompt, API `v1beta`, 60-second timeout, 1,024 output-token budget, default thinking and no SDK retries. No code fix or second request was needed. Sanitized response metadata is in ignored `.temporal/gemma-full-schema-verification.json`; no raw response or key is included. Successful full-schema inference is now verified separately from the prior mocked tests/native Temporal tests. Live PostgreSQL deployment remains unverified and no Neon migration was run. Historical failed probes described below do not represent the current live-schema gate status; one successful request is not a reliability or latency guarantee.

### Latency routing optimization (October 14)

With `AI_PROVIDER=gemma`, `AI_FAST_PATH_ENABLED=true` (default) handles structured HTTP 429, HTTP 401, HTTP 503, `CONNECTION_TIMEOUT`/`CONNECT_TIMEOUT`, and `SCHEMA_VALIDATION_ERROR`/`INVALID_PAYLOAD` without an AI request. Authentication/validation denials take precedence over retryable HTTP evidence and require human review. Conflicting connection evidence (such as HTTP 200 plus a timeout code), generic network errors, generic timeouts and unknown failures route to Gemma. No raw error-text matching is used. These rules report only the category supported by structured evidence, not an invented underlying root cause. Their confidence is a fixed heuristic for classification, never authorization or a calibrated probability.

Fast-path diagnoses pass the unchanged seven-field Pydantic schema and the same deterministic safety policy. Low confidence thresholds/human-review gates still block actions. Explicit mock mode preserves the original mock fixtures and never calls Gemma. Disable the fast path explicitly for controlled hosted-only validation; it is not silently bypassed by routine requests.

Actual source is persisted in the existing `provider` column (`deterministic`, `gemma`, `mock`) and exposed as `diagnosis.source` and audit metadata, without a migration. Deterministic outputs use `deterministic-diagnosis-v1`; hosted outputs use the selected Gemma ID; fallback/failed synthetic outputs use `mock-diagnosis-v1`. `requested_model_id` records the configured model and does not imply it was called. Historical mock/fallback/failed records are exposed as `source=mock` without data backfill. No deterministic result is labeled as a Gemma response.

The synthetic production prompt shrank from **2,439 to 2,183 characters (10.5%)**, including system instructions. It retains the exact schema and a compact example, while omitting duplicate status/code fields, timestamps and empty attempt history. Meaningful prior outcomes and allowlisted metadata remain. The shortened prompt requests a phrase/sentence for cause/explanation but does not truncate or weaken schema validation.

`AI_MAX_OUTPUT_TOKENS=1024` defaults to a bounded budget configurable from 512–2048; concise full JSON should fit, but token-exhausted/truncated output remains rejected. `AI_THINKING_LEVEL=default` omits explicit thinking configuration. Optional `minimal` and `high` match [Google's hosted Gemma 4 controls](https://ai.google.dev/gemma/docs/core/gemma_on_gemini_api); no Gemini-only thinking budget or JSON mode is assumed. Earlier probes did not prove a latency improvement from these controls, so the default was not changed. Existing request/activity/workflow timeout hierarchy and SDK retry limits remain intact.

Run `.venv/Scripts/python -B -m scripts.benchmark_diagnosis` for a network-free benchmark. Each case uses 100 warm-up iterations and 2,000 measured samples of deterministic classification + output Pydantic validation + policy only. The recorded medians were **0.0128–0.0190 ms**, with p95 **0.0170–0.0294 ms**. Input construction, database, Temporal and network time are excluded. This is not hosted Gemma latency or an endpoint latency guarantee. No new hosted inference benchmark was performed; the earlier full-schema live gate remains open. See implementation report for per-case results and final test counts.

### Output contract and timeout correction (October 14)

The production schema requires exactly seven fields: `failure_category` (one of `NETWORK_ERROR`, `RATE_LIMIT`, `AUTHENTICATION_ERROR`, `INVALID_PAYLOAD`, `TIMEOUT`, `SERVICE_UNAVAILABLE`, `UNKNOWN_ERROR`), `root_cause` (string, 1–500 characters), `explanation` (string, 1–1000 characters), `recommended_action` (one of `RETRY_WITH_BACKOFF`, `WAIT_AND_RETRY`, `USE_APPROVED_FALLBACK`, `ESCALATE`), `confidence` (finite number, 0–1), `requires_human_approval` (JSON boolean), and `alternative_actions` (array of at most four allowed actions). Extra fields, unsafe prose and incorrect types are rejected. The prompt derives constraints/enums/required fields from the unchanged Pydantic schema, omits cosmetic schema titles, and includes one explicitly synthetic shape example. It forbids Markdown and prose outside a single JSON object; missing fields are never filled or inferred.

`AI_INVALID_OUTPUT` remains the public/fallback code. Internal `AI_OUTPUT_*` codes distinguish malformed JSON, formatting, missing fields, wrong types, enums, confidence, extra fields, duplicate keys, non-object JSON, unsafe prose, length constraints, missing/empty response text and token exhaustion. Only recognized schema field names are retained; unexpected key names, values, provider messages and raw responses are excluded. Details persist in the existing diagnosis result audit; no new migration is needed. Invalid output follows the existing fallback/escalation policy.

AI request timeout defaults to 60 seconds and is configurable from 1–60 seconds. New diagnosis activities have 75-second start-to-close and 240-second schedule-to-close budgets (three delivery attempts plus queue/retry headroom). Other activities retain 30 seconds / 120 seconds; workflow execution/run limits remain 20 minutes. Temporal patch `diagnosis-timeouts-v1` preserves old histories' diagnosis budget during replay. The provider also caps its request against the actual activity budget minus 10 seconds, retaining headroom for legacy 30-second activities. SDK retries stay disabled. Optional explicit thinking control is omitted, matching the earlier probe that returned a response; no unsupported JSON MIME/schema API feature is enabled. This omission does not prove that thinking control caused the prior HTTP 500.

A longer timeout permits longer waits; it does not ensure provider success or schema fidelity. Pre-commit Temporal retries can repeat inference and consume free-tier quota. The October 14 live probe made exactly one request using the actual production prompt: response received in **23.383 seconds**, rejected by the provider text-presence/size guard before JSON validation, with safe fallback and no recovery actions. That guard still had a coarse code; afterward, missing/empty/oversized/token-limited envelope failures were separately classified and tested offline. The response was not retained, so its precise envelope branch cannot be reconstructed; no second live call was made. Full-schema inference remains unverified. The earlier full-response rejection likewise cannot be classified retrospectively.

See `IMPLEMENTATION.md` for final test results. `.env` and `AI_PROVIDER=mock` were not changed. Live PostgreSQL, remote hosting and production resilience are not claimed.

The official `google-genai` SDK uses the Google Generative Language API, explicitly selecting Gemma rather than Gemini. On October 13, 2026, model listing with the configured key returned `models/gemma-4-26b-a4b-it` and `models/gemma-4-31b-it`. The smaller `gemma-4-26b-a4b-it` is the default model. See [hosted Gemma documentation](https://ai.google.dev/gemma/docs/core/gemma_on_gemini_api) and [pricing](https://ai.google.dev/gemini-api/docs/pricing). Listing verifies catalog access, not successful generation. Two bounded synthetic generation requests failed; the diagnostic retry confirmed HTTP 500. Real inference is **not validated**. No Gemini substitution, billing upgrade, GPU, Docker, or WSL is used.

Default `AI_PROVIDER=mock` preserves deterministic behavior and avoids accidental inference when a key is present. To opt in, configure these privately in the existing `.env` or worker environment, retaining all existing values:

```dotenv
AI_PROVIDER=gemma
AI_MODEL=gemma-4-26b-a4b-it
# GEMINI_API_KEY is the existing private key, never a value copied from docs.
AI_TIMEOUT_SECONDS=60
AI_FALLBACK_ENABLED=true
AI_MIN_CONFIDENCE=0.75
```

Only the two verified Gemma identifiers are accepted. SDK retries are disabled; request timeout follows the configured 1–60-second limit and actual activity headroom described above. Temporal retains three delivery attempts. Inference may repeat after a crash before commit or during concurrent deliveries; a committed diagnosis audit prevents another call on redelivery. Incident locks and a unique diagnosis key ensure one persisted result and idempotent mock effects. No exactly-once AI request or production latency guarantee is claimed.

The existing `recovery_step` activity performs diagnosis. Workflow business flow, identifier-only Temporal payloads, outbox behavior, deterministic IDs, and mock adapter remain intact; diagnosis timeout commands use the replay-safe patch described above. The activity reads scoped evidence, closes the read transaction, calls the provider, validates JSON/policy, then rechecks enabled tenant/workflow/integration scope inside the write transaction. Diagnosis, policy, state transition, and result audit commit atomically. Temporal history carries only fixed recovery codes, not prompts, model prose, or keys.

Input is deliberately lossy: raw webhook messages remain discarded and stored as `[REDACTED]`. Gemma receives only allowlisted failure codes, optional numeric `error.http_status` (integer 100–599), timestamp, allowlisted integration/workflow kinds, and bounded mock-attempt outcome codes. It receives no tenant IDs, external workflow names, execution IDs, raw customer context, URLs, or secrets. Missing evidence cannot be reconstructed. The prompt treats evidence as untrusted and forbids invented facts, tools, shell commands, and secret disclosure.

Pydantic accepts seven failure categories and four advisory actions. Extra/missing fields, duplicate JSON keys, markdown wrappers, non-finite/out-of-range confidence, incorrect types, excessive text, and suspicious prose are rejected. The key is checked against returned text; raw responses and provider/validation exception details are never persisted or logged. Prose filters are defense in depth, not a universal sensitive-data detector; allowlisted inputs are the primary privacy control. API clients must render returned prose as untrusted text.

Policy independently checks evidence, category, confidence threshold, and human-review flags. Authentication/payload failures, unknown evidence, low confidence, or approval requirements escalate. Confidence alone grants no permission. Retry/backoff and a registered mock fallback are the only executable behaviors; fallback requires policy permission. A `USE_APPROVED_FALLBACK` recommendation produces a failed synthetic primary attempt then the permitted mock fallback using the existing workflow. There is no approval execution endpoint or real external action.

Provider timeout/authentication/rate-limit/unavailability and invalid output use fixed codes. With fallback enabled, original mock fixtures preserve Checkpoint 2 behavior and diagnosis status is `FALLBACK`; with fallback disabled, status is `FAILED` and recovery escalates. Valid but unsafe/low-confidence outputs are `POLICY_REJECTED` and escalate without silently replacing the recommendation. Explicit mock mode is labeled `MOCK`.

Revision `0003` adds `incident_diagnoses` with same-tenant foreign keys, a unique tenant/incident pair, status/confidence constraints, diagnosis fields, provider/requested and actual model IDs, timestamp, fallback reason, and policy result. Revisions `0001`/`0002` and historical records are unchanged; there is no backfill. Review/apply `0003` separately before deploying against a persistent database. **No live Neon migration was executed during Checkpoint 3.** The optional development migration command understands additive upgrades to `0003` and retains development/public-schema/baseline guards.

`GET /api/v1/incidents/{incident_id}/recovery` includes a nullable `diagnosis` object: status, category, root cause, explanation, recommendation, confidence, human-review flag, alternatives, provider, actual/requested model, timestamp, fallback reason, and policy reason. `null` means no diagnosis record, including historical incidents. The response `status` remains the recovery outcome; `mode=mock-only` describes execution. Existing bearer authorization and 401/404 behavior apply. Timeline entries include fixed diagnosis/model/policy/fallback codes, never prompts or raw responses.

Routine tests mock model transport and never call live AI. Run SQLite tests from `backend/` in a separate test terminal:

```powershell
Remove-Item Env:TEST_DATABASE_URL -ErrorAction SilentlyContinue
$env:DATABASE_URL = 'sqlite:///:memory:'
$env:AI_PROVIDER = 'mock'
$env:AI_MODEL = 'gemma-4-26b-a4b-it'
$env:GEMINI_API_KEY = ''
$env:TEMPORAL_API_KEY = ''
$env:TEMPORAL_TLS_ENABLED = 'false'
$env:RUN_TEMPORAL_INTEGRATION = '0'
.venv/Scripts/python -B -m pytest -q -p no:cacheprovider --basetemp ".temporal/unit-$([guid]::NewGuid().ToString('N'))"
# Separate native server run: Gemma transport remains mocked.
$env:RUN_TEMPORAL_INTEGRATION = '1'
$env:TEMPORAL_CLI_PATH = (Resolve-Path .temporal/cli/temporal.exe).Path
.venv/Scripts/python -B -m pytest -q tests/test_temporal_integration.py tests/test_ai_temporal.py -p no:cacheprovider --basetemp ".temporal/native-$([guid]::NewGuid().ToString('N'))"
```

SQLite migration tests use fresh disposable databases. Native tests verify actual Temporal execution/replay/activity redelivery/worker restart with mocked diagnosis responses. They do not prove real Gemma inference or live PostgreSQL behavior. See `IMPLEMENTATION.md` for results. The Checkpoint 2 descriptions below document the inherited behavior; this section describes the diagnosis extension.

## Docker-free setup with Neon (PowerShell)

Install Python 3.11+ on Windows. Neon hosts PostgreSQL; Docker, WSL2, a local PostgreSQL server, and `psql` are unnecessary. Use a development database or branch in your Neon project. From the repository root:

```powershell
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

Edit `backend/.env` privately. Copy the connection string from Neon's **Connect** dialog for the intended development branch, database, and role. Select a **direct** connection for migrations and schema tests. Change the URL scheme from `postgresql://` to `postgresql+psycopg://`; retain the credentials and query options. The installed `psycopg[binary]` package supplies Psycopg 3 and its Windows binary dependencies. Keep `sslmode=require&channel_binding=require`, as supplied by Neon. Percent-encode special characters in manually entered credentials. See [Neon's connection guide](https://neon.com/docs/get-started-with-neon/connect-neon).

The following is a template, not a working credential:

```dotenv
DATABASE_URL=postgresql+psycopg://<role>:<encoded-password>@<direct-neon-host>/<database>?sslmode=require&channel_binding=require
APP_ENV=development
```

The localhost defaults in `.env.example` are placeholders and do not connect to Neon. Environment variables override `.env`; remove an unintended `DATABASE_URL` environment variable before checking. Run commands from `backend/` so `.env` resolves correctly. Do not paste real URLs into terminal commands, logs, screenshots, or Git. `.env` and `.env.*` are ignored by Git, except `.env.example`; never put secrets in that example.

Set `N8N_WEBHOOK_SECRET` to a fresh random secret of at least 32 characters (for example, generate one with `.venv/Scripts/python -c "import secrets; print(secrets.token_urlsafe(32))"`). Keep it private. Use a dedicated secret/environment variable for each integration. Do not reuse database credentials, webhook secrets, or tenant read tokens.

Check live connectivity, then initialize only an empty development database:

```powershell
.venv/Scripts/python -m scripts.check_database
.venv/Scripts/python -m scripts.check_database --migrate-empty-dev
```

The check runs real `SELECT 1`, verifies client-side TLS, and reports public tables and the Alembic revision without printing the URL. Neon terminates TLS at its proxy, so `pg_stat_ssl` does not report the client TLS connection. The empty-database migration option requires `APP_ENV=development`, the `public` default schema, and no existing user relations before applying revisions `0001` through `0003` in a transaction. If already at head, it checks tables and model drift. It refuses an unversioned or partially migrated database with existing objects: review those manually; never reset, downgrade, or delete application data to force initialization. These upgrades create tables, indexes, and constraints without deleting data. Downgrades are used only inside disposable test databases. No live migration was run during Checkpoint 3.

Expected tables: `tenants`, `integrations`, `workflows`, `incidents`, `audit_logs`, `recovery_attempts`, `recovery_outbox`, `incident_diagnoses`, plus Alembic's `alembic_version`. No demo tenants or incidents are inserted by the connectivity/migration check.

If connectivity fails, confirm the selected branch and role, URL scheme, SSL options, and outbound TCP access to port 5432. Windows socket error 10013 indicates blocked network access; permit the Python process/network connection and retry. Generic driver error details are suppressed because they may contain secrets.

Provision a synthetic tenant and start the API:

```powershell
.venv/Scripts/python -m scripts.provision --tenant-name "Acme Demo Store" --workflow-external-id notify-orders --secret-env N8N_WEBHOOK_SECRET
.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Provisioning prompts privately for a separate random tenant read token (32-512 characters), stores only its SHA-256 hash, and prints the tenant, integration, and workflow IDs. Save the read token locally. No provisioning HTTP endpoint or user login is provided. To provision the second synthetic tenant, add a different secret variable to `.env` and repeat with `--tenant-name "Northstar Demo Studio" --secret-env NORTHSTAR_WEBHOOK_SECRET`. Choose a different read token. Restart the API after changing process environment variables.

The integration stores only the environment variable name (`secret_ref`), not its secret value. Environment variables override `.env`; missing/short secrets fail closed with 503. References must be configured by the operator, never by webhook callers. Revocation uses the integration `enabled` flag; rotation updates its referenced secret. A secrets manager and user authentication are future work.

On Linux/macOS, replace `.venv/Scripts/python` with `.venv/bin/python`. Run backend commands from `backend/` so `.env` resolves correctly. Tables are initialized only by migrations; the API never calls `create_all`.

## Send a synthetic event

In a second terminal, from `backend/`, replace the integration UUID below with the provisioning output:

```powershell
.venv/Scripts/python -m scripts.send_failure --integration-id <integration-uuid> --event-id demo-001
```

The response is `202` with `incident_id`, `status: RECEIVED`, and `duplicate: false`. Repeat with the same event ID within the timestamp window to receive the same incident with `duplicate: true`. The helper signs and sends the identical byte string. It does not invoke n8n or demonstrate a real external recovery.

Read an incident using the separate tenant credential:

```powershell
$readToken = Read-Host "Tenant read token" -AsSecureString
$credential = [System.Net.NetworkCredential]::new('', $readToken)
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/incidents/<incident-uuid>" -Headers @{Authorization = "Bearer $($credential.Password)"}
```

`GET /health` returns `{"status":"ok"}`. It is a liveness check, not a database readiness check. API schema: `http://127.0.0.1:8000/docs`.

## Webhook contract

`POST /api/v1/events/failure` requires:

- `Content-Type: application/json`
- `X-Integration-ID: <integration UUID>` (public identifier)
- `X-Webhook-Signature: sha256=<64 lowercase hexadecimal characters>`

Compute HMAC-SHA256 with that integration's secret over **exact raw request bytes**, without parsing/reserializing JSON. The timestamp is inside the signed JSON, so it cannot be refreshed without signing again. There is no unsigned timestamp header and no bearer credential for ingestion.

```json
{
  "schema_version": "1.0",
  "event_id": "event-1042",
  "timestamp": "2026-10-13T06:00:00Z",
  "source": "n8n",
  "source_execution_id": "exec-1042",
  "workflow_external_id": "notify-orders",
  "failed_step": "send_customer_confirmation",
  "operation_id": "notify-order-1042",
  "error": {"category": "PROVIDER_UNAVAILABLE", "message": "HTTP 503"}
}
```

Use a current, timezone-aware ISO timestamp (the example timestamp will expire). References are nonempty, at most 200 characters, and use letters, digits, `_ . : / -`; categories use uppercase letters, digits, and underscores (at most 100 characters). References should contain opaque synthetic IDs, not personal information or credentials. Error messages have a 4000-character input cap and are replaced wholesale with `[REDACTED]` before storage. Only the structured category is retained as sanitized error detail. Raw request bodies, context, and arbitrary metadata are never persisted. Unknown fields, including `tenant_id` and `context`, are rejected at this checkpoint. `schema_version` defaults to `1.0` if omitted.

The authenticated integration determines the tenant. The workflow must be enabled and registered to that integration and tenant. Event IDs are unique per tenant; an additional unique `(tenant_id, source, source_execution_id, failed_step)` constraint implements the planning documents' dedup key. Both constraints are permanent in Checkpoint 1. Use stable event IDs on retries. A duplicate is accepted only after authentication, schema validation, timestamp validation, and workflow resolution. A stale replay is rejected, even if previously received. Conflicting identifiers resolve to an existing incident without modifying it; there is no payload merging or new recovery execution.

The incident, `INCIDENT_RECEIVED` audit entry, and recovery outbox row commit atomically before returning 202. Acceptance means durable queueing; Temporal may be temporarily unavailable. Duplicate deliveries produce no extra audit entry. Cross-tenant references are also constrained by composite foreign keys. Incident reads use a hashed, high-entropy tenant read token; missing/invalid credentials return 401. Foreign-tenant and unknown incident UUIDs both return 404.

Errors: 401 invalid/revoked webhook credentials or timestamp outside tolerance (past or future); 404 unknown/disabled workflow; 413 excessive body size; 415 unsupported content type; 422 malformed schema/JSON; 503 missing integration secret. Validation errors do not echo payloads.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| DATABASE_URL | Local development placeholder | SQLAlchemy URL using `postgresql+psycopg` |
| APP_ENV | development | Environment label; does not automatically configure deployment security |
| WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS | 300 | Accepted absolute clock skew, 1-3600 seconds |
| MAX_WEBHOOK_BODY_BYTES | 65536 | Request body bound, 1024-1048576 bytes |
| N8N_WEBHOOK_SECRET | unset | Example integration secret reference; at least 32 characters |

API and n8n clocks must be synchronized. Shared read credentials are a minimal checkpoint authentication mechanism, not a full user/role model. Rate limiting, TLS deployment, encrypted secret storage infrastructure, retention policies, and immutable audit enforcement remain outside this checkpoint. No production-readiness claim is made.

## Tests

```powershell
.venv/Scripts/python -m pytest -q
```

The default suite migrates a fresh SQLite database for each test with foreign keys enabled. It covers the seven requested cases plus future timestamps, byte tampering, revocation, workflow scope, redaction, concurrency, database tenant constraints, migration drift, and upgrade/downgrade.

To exercise the same suite on PostgreSQL, use a **dedicated test database or Neon branch**, not a production database. The database role must be able to create schemas. Configure `TEST_DATABASE_URL` privately in the process environment with an explicit `postgresql+psycopg` URL, then run:

```powershell
.venv/Scripts/python -m scripts.test_postgres
```

For a development database, the existing suite can also run in isolated schemas in that database:

```powershell
.venv/Scripts/python -m scripts.test_postgres --use-development-database
```

This fallback requires `APP_ENV=development`; an explicit `TEST_DATABASE_URL` takes precedence. The runner does not print the URL and redacts connection credentials from captured pytest output. For Neon it uses the direct hostname (removing `-pooler` when present), because fixtures rely on session-level `SET search_path`, which transaction pooling does not preserve. See [Neon's pooling guidance](https://neon.com/docs/connect/connection-pooling). Each test migrates, populates, and removes only its own random `test_<uuid>` schema. The upgrade/downgrade test operates inside that schema, preserving `public` application data. The runner uses a fresh temporary directory and disables pytest's cache to avoid Windows ACL conflicts between execution identities.

Do not run schema tests alongside other migration tooling. If a process is interrupted, test schemas may remain; inspect them rather than deleting unrelated objects. Inspect offline PostgreSQL DDL with `.venv/Scripts/python -m alembic upgrade head --sql`.

## Temporal development on native Windows

The official Windows CLI was validated with Temporal Python SDK 1.34.0 using `WorkflowEnvironment.start_local(dev_server_existing_path=...)`. The initial automatic SDK download timed out; downloading the official Windows archive and supplying its path worked. This local test environment runs a real server without time skipping. See [Temporal CLI setup](https://docs.temporal.io/cli/setup-cli) and [SDK testing](https://python.temporal.io/temporalio.testing.WorkflowEnvironment.html).

From `backend/`, download the native executable once (the cache is ignored by Git):

```powershell
New-Item -ItemType Directory -Force .temporal | Out-Null
Invoke-WebRequest -Uri 'https://temporal.download/cli/archive/latest?platform=windows&arch=amd64' -OutFile .temporal/temporal-windows.zip
Expand-Archive -LiteralPath .temporal/temporal-windows.zip -DestinationPath .temporal/cli -Force
```

Use `arch=arm64` for Windows ARM. Start the server in one terminal:

```powershell
.temporal/cli/temporal.exe server start-dev --ip 127.0.0.1 --db-filename .temporal/rebootx-server.db
```

gRPC defaults to `127.0.0.1:7233`; UI defaults to `http://127.0.0.1:8233`. `--db-filename` retains server state across server stops; without it the development server loses executions on exit. The development server is for local use. Production server persistence, availability, and remote credentials are operator responsibilities; Temporal Cloud can incur charges and is not selected automatically.

For the existing Checkpoint 1.5 development database, apply the reviewed additive migration before starting the API, worker, or dispatcher:

```powershell
.venv/Scripts/python -m scripts.check_database --upgrade-dev
```

This accepts only development revision `0001` upgrading to `0002` (or validates an already current schema). The PostgreSQL upgrade adds nullable columns, constraints, indexes, and an empty outbox; it does not drop, truncate, delete, or backfill existing incidents. Historical incidents remain readable and show `NOT_QUEUED`. Fresh empty databases use `--migrate-empty-dev`. Do not run downgrades against application data.

Add the following non-secret settings to `.env` if desired; they are also the defaults:

```dotenv
TEMPORAL_ADDRESS=127.0.0.1:7233
TEMPORAL_NAMESPACE=default
TEMPORAL_TASK_QUEUE=rebootx-recovery-v1
TEMPORAL_TLS_ENABLED=false
TEMPORAL_API_KEY=
```

For a remote server, set its address and existing namespace, enable TLS, and configure the API key privately if that server uses API-key authentication. Remote plaintext connections and any API key without TLS are refused. mTLS client-certificate configuration is not implemented. API, dispatcher, and worker must use the same database, namespace, and task queue. Keep those settings stable while events are queued; changing namespace can create a separate execution with the same workflow ID.

Start the worker and dispatcher in separate terminals, from `backend/`:

```powershell
.venv/Scripts/python -m app.temporal.worker
```

```powershell
.venv/Scripts/python -m app.temporal.dispatcher
```

FastAPI can accept webhooks while Temporal is unavailable because it only commits the incident, audit, and outbox transaction. The dispatcher claims due rows with a 60-second lease, commits before calling Temporal, then acknowledges using its lease token. PostgreSQL uses `FOR UPDATE SKIP LOCKED`; conditional writes prevent stale acknowledgements. Starts use `rebootx:recovery:v1:<tenant UUID>:<incident UUID>` with reject-duplicate reuse policy and fail-on-conflict policy. Already-started executions count as dispatched. Start/connection failures retain a fixed, secret-safe error code and retry with exponential backoff capped at 60 seconds. A failed database acknowledgement leaves the lease reclaimable. This is a database outbox, not an in-memory queue or an API fire-and-forget task.

## Mock recovery lifecycle and read APIs

| Requested stage | Persisted incident state |
|---|---|
| ACCEPTED | VALIDATING (initial ingestion remains RECEIVED) |
| DIAGNOSING | DIAGNOSING |
| RECOVERY_PLANNED | PLANNED |
| RECOVERING | EXECUTING |
| VERIFYING | VERIFYING |
| RECOVERED / ESCALATED | RECOVERED / NEEDS_ATTENTION |

`IncidentRecoveryWorkflow` receives version-1 dataclass inputs containing only incident, tenant, registered workflow, integration, and correlation UUIDs. Workflow code performs no database, HTTP, random, or wall-clock operations. All database mutations are transactional service calls inside activities; Temporal timers implement the two-second mock rate-limit delay.

Every step revalidates the incident's tenant, workflow, integration, and enabled registration. PostgreSQL locks the tenant-scoped incident row; SQLite reserves a write transaction. Unique `(tenant_id, incident_id, logical_key)` constraints protect recovery attempts and audit steps. Retried activities return the committed result for that logical step without regressing state or repeating attempts. Mutations, mock outcomes, failure reasons, verification, and audit entries commit together.

Each activity allows at most three delivery attempts, with one-to-five-second retry intervals, a 30-second start-to-close limit, and a two-minute schedule-to-close limit. Business recovery allows exactly one `MOCK_RETRY` and, on failure, one `MOCK_FALLBACK`. The workflow has a 20-minute execution/run limit and no automatic workflow-level retries. Persistent activity failure attempts a bounded escalation; a continuing database outage or revoked scope may also prevent escalation persistence and leave a failed execution for operator review.

| Synthetic error category | Mock behavior |
|---|---|
| TRANSIENT_NETWORK_FAILURE / NETWORK_RETRY_SUCCESS | Retry succeeds; verify |
| RATE_LIMIT | Wait two seconds; retry succeeds; verify |
| PROVIDER_UNAVAILABLE / NETWORK_FALLBACK_SUCCESS | Retry fails; fallback succeeds; verify |
| NETWORK_BOTH_FAIL | Retry and fallback fail; escalate |
| NETWORK_VERIFY_FAIL | Retry succeeds; verification fails; escalate |
| AUTHENTICATION_FAILURE / INVALID_PAYLOAD | Immediate escalation; no retry/fallback |
| Any other category | UNKNOWN_FAILURE escalation |

Only fixed fixtures are consulted; free-form error text is discarded. `MOCK_VERIFIED` means the synthetic result met the mock criterion. It is not external provider acceptance or delivery evidence. All attempts use `mock-only-v1`; no production credentials, HTTP adapters, shell actions, customer data transforms, or Gemma calls exist. High-risk actions remain blocked.

Use the existing tenant bearer read token for these new endpoints:

- `GET /api/v1/incidents/{incident_id}/recovery`: state, mock verification, escalation reason, workflow ID, and dispatch status/error.
- `GET /api/v1/incidents/{incident_id}/attempts`: actions, mock adapter, outcomes, failure reasons, and timestamps.
- `GET /api/v1/incidents/{incident_id}/timeline`: tenant-scoped redacted audit entries.

Missing/invalid credentials return 401. Another tenant's incident and an unknown incident both return 404. Structured orchestration logs contain allowlisted UUIDs and fixed codes, never raw exception messages, connection strings, or tokens.

## Real Temporal tests and validation boundaries

The default suite includes the original regression tests, service/outbox tests, SDK `ActivityEnvironment` tests, and a mocked workflow driver. It explicitly skips the two real-server tests. Run the latter against a fresh native server launched by the SDK:

```powershell
$env:RUN_TEMPORAL_INTEGRATION = '1'
.venv/Scripts/python -m pytest -q tests/test_temporal_integration.py
Remove-Item Env:RUN_TEMPORAL_INTEGRATION
```

The cached `.temporal/cli/temporal.exe` is discovered automatically. Alternatively set `TEMPORAL_CLI_PATH` to an installed native executable. SDK `start_local()` can download a CLI when no path exists, but that requires network access. If Windows pytest temporary-directory ACLs conflict between identities, use a fresh `--basetemp .temporal/pytest-<unique-id>` and `-p no:cacheprovider`.

These opt-in tests validate the lifecycle matrix, real activity retry after a committed action loses its acknowledgement, duplicate starts on a real server, deterministic history replay, and an actual worker process exiting after its mock retry commit then restarting. Tests use disposable SQLite data by default. For real Temporal with isolated live PostgreSQL persistence, run:

```powershell
.venv/Scripts/python -m scripts.test_postgres --use-development-database --temporal-only
```

The regular PostgreSQL command keeps real-server tests separate by default. Raw schema fixtures reject pooled URLs, and Alembic refuses test migrations if the required random schema is not active. No test downgrades Neon `public` tables.

Worker restart durability was validated against a live native development server with both SQLite and isolated live Neon application persistence. This does not establish server-restart durability, remote Temporal availability, live provider safety, or production resilience. Workflow timeouts/failures, revoked registration, exhausted infrastructure retries, and orphaned historical incidents require operator review; automated reconciliation/backfill/admin retry endpoints are deferred.

## Scope reconciliation

The implemented backend stays in `backend/`. Its `/api/v1` HMAC webhook and separate hashed tenant read token remain authoritative; the planning documents' illustrative `/v1` bearer webhook is not the deployed contract. `202` means the incident and durable outbox event committed, not that a Temporal worker has already started. Request-supplied tenant IDs and arbitrary context remain forbidden. Checkpoint 3 adds configurable advisory Gemma diagnosis and deterministic policy to the existing Temporal mock actions. Successful live inference remains blocked by the observed provider failure. Real notification adapters, human approval execution, users/roles, operation reconciliation, frontend, and n8n templates remain future work.
