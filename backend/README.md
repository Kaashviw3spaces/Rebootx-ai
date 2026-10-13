# Checkpoint 2 backend: durable Temporal mock recovery

Python 3.11+; FastAPI, SQLAlchemy 2.x, PostgreSQL, Pydantic v2, Alembic, pytest. This checkpoint durably queues incidents for Temporal and runs mock diagnosis/retry/fallback/verification. It never sends notifications or invokes real automation adapters.

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

The check runs real `SELECT 1`, verifies client-side TLS, and reports public tables and the Alembic revision without printing the URL. Neon terminates TLS at its proxy, so `pg_stat_ssl` does not report the client TLS connection. The migration option requires `APP_ENV=development`, the `public` default schema, and no existing user relations before applying revisions `0001` and `0002` in a transaction. If already at head, it checks tables and model drift. It refuses an unversioned or partially migrated database with existing objects: review those manually; never reset, downgrade, or delete existing application data to force initialization. This checkpoint's upgrade creates tables, indexes, and constraints without deleting data. Its downgrade deletes tables and is used only inside disposable test schemas.

Expected tables: `tenants`, `integrations`, `workflows`, `incidents`, `audit_logs`, `recovery_attempts`, `recovery_outbox`, plus Alembic's `alembic_version`. No demo tenants or incidents are inserted by the connectivity/migration check.

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

The implemented backend stays in `backend/`. Its `/api/v1` HMAC webhook and separate hashed tenant read token remain authoritative; the planning documents' illustrative `/v1` bearer webhook is not the deployed contract. `202` means the incident and durable outbox event committed, not that a Temporal worker has already started. Request-supplied tenant IDs and arbitrary context remain forbidden. This checkpoint implements Temporal with deterministic mock diagnosis and mock actions. Gemma, real notification adapters, human approval execution, users/roles, operation reconciliation, frontend, and n8n templates remain future work.
