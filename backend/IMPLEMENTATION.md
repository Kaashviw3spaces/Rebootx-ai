# Checkpoint 2 implementation report

## Delivered behavior

An authenticated webhook atomically commits the incident, its existing receipt audit, and a unique recovery outbox event. The independent dispatcher uses short claims, 60-second leases, fenced acknowledgements, bounded RPC calls, and exponential retry. A deterministic tenant/incident Temporal workflow ID with reject-duplicate policy resolves lost start acknowledgements safely. API acceptance does not depend on Temporal availability.

`IncidentRecoveryWorkflow` runs version-1 identifier-only dataclass inputs. Database and other side effects stay in activities/services. The lifecycle uses existing state constraints: RECEIVED -> VALIDATING -> DIAGNOSING -> PLANNED -> EXECUTING -> VERIFYING -> RECOVERED, or NEEDS_ATTENTION escalation. Fixed mock fixtures classify network, rate-limit, authentication, invalid payload, and unknown failures. One mock retry, one fallback if necessary, and verification are bounded; no real external actions or Gemma calls exist.

Same-tenant incident locks, scoped registration checks, transactional result audits, and unique logical attempt/audit keys make activity redelivery idempotent. SQLite uses BEGIN IMMEDIATE because it ignores row locks. Revocation fails closed. New read endpoints preserve the existing tenant bearer-token model and 401/404 behavior. Logs and persisted dispatch errors use fixed codes and allowlisted identifiers; raw database/Temporal error messages and credentials are excluded.

## Files created

- `backend/alembic/versions/0002_temporal_recovery.py`
- `backend/app/schemas/recovery.py`
- `backend/app/services/recovery.py`
- `backend/app/temporal/__init__.py`
- `backend/app/temporal/schemas.py`
- `backend/app/temporal/client.py`
- `backend/app/temporal/logging.py`
- `backend/app/temporal/activities.py`
- `backend/app/temporal/workflows.py`
- `backend/app/temporal/worker.py`
- `backend/app/temporal/dispatcher.py`
- `backend/tests/conftest.py`
- `backend/tests/test_recovery.py`
- `backend/tests/test_temporal_integration.py`
- `backend/tests/restart_worker.py`

## Files modified

- `.gitignore`: ignore native Temporal binaries, server persistence, and test artifacts under `backend/.temporal/`.
- `backend/.env.example`: non-secret Temporal settings only.
- `backend/requirements.txt`: official `temporalio>=1.34,<2` SDK.
- `backend/app/core/config.py`: local/remote Temporal address, namespace, queue, TLS, and SecretStr API key.
- `backend/app/models/entities.py`: outbox, verification/escalation fields, nullable logical keys, uniqueness.
- `backend/app/services/incidents.py`: atomic incident/audit/outbox handoff.
- `backend/app/api/routes.py`: three tenant-authorized recovery read endpoints.
- `backend/scripts/check_database.py`: guarded additive development upgrade and outbox verification.
- `backend/scripts/test_postgres.py`: optional real Temporal tests with isolated Neon persistence.
- `backend/alembic/env.py`: refuse test migrations when the required isolated schema is not active.
- `backend/tests/test_backend.py`: move the existing database fixture to conftest; existing assertions retained.
- `backend/pytest.ini`: explicit real-server and worker-restart markers.
- `backend/README.md`, `backend/IMPLEMENTATION.md`, `docs/ARCHITECTURE.md`, `docs/EXECUTION_PLAN.md`: implementation boundaries, Windows setup, operation, and validation evidence.

`backend/.env` was not modified during Checkpoint 2. No commits or pushes were made. Native CLI archives/executables, pytest temporary data, and compiled bytecode are ignored artifacts, not source changes.

## Dependencies and migration

Installed SDK 1.34.0 in the existing virtual environment. Its added dependencies are `nexus-rpc`, `protobuf`, and `types-protobuf`; no Docker, WSL, container, cloud subscription, or production credentials are required.

Revision `0002` follows `0001`. It creates `recovery_outbox`, adds nullable recovery/verification fields and nullable logical keys, and adds same-tenant uniqueness constraints. Historical records remain intact; historical incidents are not silently queued. Offline PostgreSQL upgrade SQL was generated and checked to contain no DROP TABLE, TRUNCATE, or DELETE. SQLite batch operations are confined to disposable test databases. Destructive downgrade tests operate only inside the isolated fixture schema/database. Live application downgrades are not run.

## Validation evidence

### Post-crash revalidation (October 13, 2026)

- Inspected the saved implementation and preserved the existing Checkpoint 2 code.
- Original SQLite suite: **39 passed, 2 skipped** in 6.03 seconds.
- Reproduced lease-fencing acknowledgement logging with two failing regression cases: a reclaimed lease incorrectly logged either dispatch success or retry scheduling.
- Fixed `OutboxDispatcher.dispatch_one` to log success/retry scheduling only when `finish` accepts the acknowledgement; rejected acknowledgements emit `dispatch_acknowledgement_rejected`. Regression cases transfer the lease to a second dispatcher and verify its ownership and ability to acknowledge are preserved.
- Final SQLite suite: **41 passed, 2 skipped** in 7.35 seconds, including both new regression cases. Existing migration/model comparison and historical-record preservation tests passed against disposable SQLite databases; revision `0002` remains the head following `0001`.
- Native Temporal integration: **2 passed** in 45.04 seconds using the existing `.temporal/cli/temporal.exe`. Verified eight mock lifecycle scenarios, committed-activity redelivery, duplicate starts, deterministic replay, and actual worker-process crash/restart without duplicate recovery attempts.
- Each test subprocess removed `TEST_DATABASE_URL`, overrode `DATABASE_URL` with `sqlite:///:memory:`, cleared the Temporal API key, and used fresh UUID-named pytest base directories beneath ignored `.temporal/`. The shared fixture therefore selected a separate disposable SQLite database for each test. Real-server tests were disabled for the unit run and enabled only for the separate native integration run with an explicit local CLI path.
- Used `-B`, `-p no:cacheprovider`, and `--basetemp` for test runs. In-memory Python syntax checks and `git diff --check` passed. The existing Starlette/httpx deprecation warning remains non-failing.
- No dependencies installed, live Neon connections/migrations, external recovery actions, commits, or pushes. SQLite upgrade/downgrade operations were confined to newly created disposable test databases. Current live Neon revision and remote Temporal/server-restart durability were not revalidated.

The validation entries below describe the earlier implementation session, not new live-database operations during post-crash validation.

- SQLite regression/unit suite: **39 passed, 2 skipped**. Includes all 27 original tests and 12 new service, SDK activity-environment, mocked workflow, outbox, security, and migration-preservation tests.
- Native Temporal integration: **2 passed** against CLI 1.9.1 / server 1.32.0 on Windows with SDK 1.34.0. Covers eight lifecycle fixtures, real activity retries after committed effects lose ACKs, duplicate starts, deterministic replay, and actual worker-process crash/restart. The server stayed alive while a child worker exited abruptly after committing MOCK_RETRY; a new worker completed the execution without creating a second attempt.
- Live PostgreSQL regression/unit suite: **39 passed, 2 skipped** in 756.00 seconds. All original and new recovery/outbox cases used randomly named isolated Neon schemas; the two real Temporal tests were explicitly separate.
- Combined native Temporal + live PostgreSQL integration: **2 passed** in 186.70 seconds. Real-server lifecycle/retry/duplicate/replay and actual worker-process crash/restart were repeated with isolated Neon application persistence. Test migrations explicitly required the generated test schema.
- Live migration: **0001 -> 0002 applied successfully** to the configured Neon development database after test completion. SELECT 1 and client TLS passed; Alembic found no model drift. All six pre-existing application table row counts were unchanged (zero), the new outbox was empty, and no test schemas remained. No public data was deleted or historical recovery queued.
- Syntax: compileall passed for app, scripts, tests, and Alembic.
- Dependencies: pip check passed.
- Wrong-schema migration guard: passed; an intentionally mismatched public/test schema was rejected before any DDL. Pooled URLs are refused by the raw test fixture, and the runner selects direct Neon connections.
- Each pytest validation reports the existing Starlette/httpx deprecation warning; it is non-failing.

The first automatic native CLI download timed out. The official Windows archive worked with `start_local(dev_server_existing_path=...)`; this confirms native support rather than assuming a Linux binary works. An initial concurrent SQLite activity test exposed a missing write reservation and was fixed with BEGIN IMMEDIATE; the final SQLite results above follow that correction.

## Startup and test commands

From `backend/`, after installing requirements and configuring the ignored `.env`:

```powershell
.venv/Scripts/python -m scripts.check_database --upgrade-dev
.temporal/cli/temporal.exe server start-dev --ip 127.0.0.1 --db-filename .temporal/rebootx-server.db
```

Separate terminals:

```powershell
.venv/Scripts/python -m app.temporal.worker
.venv/Scripts/python -m app.temporal.dispatcher
.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Testing:

```powershell
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m scripts.test_postgres --use-development-database
.venv/Scripts/python -m scripts.test_postgres --use-development-database --temporal-only
$env:RUN_TEMPORAL_INTEGRATION = '1'
.venv/Scripts/python -m pytest -q tests/test_temporal_integration.py
Remove-Item Env:RUN_TEMPORAL_INTEGRATION
```

Remote servers require TLS; API-key authentication is supported and stored as SecretStr. mTLS client certificates are not configured. Worker/dispatcher reuse their configured Temporal client; bounded connect/start calls and durable database retry govern outages. See README for the full setup and environment variables.

## Limitations and Checkpoint 3

This validates worker-restart recovery on a running native development server with both SQLite and isolated live Neon application persistence, not server-restart durability, remote hosting, production resilience, or external adapter safety. Remote TLS/API-key connectivity has no configured endpoint to validate. A continuing database outage, revoked registration, or workflow deadline can leave a failed/timed-out execution or stale state for operator reconciliation; automated repair/backfill/admin retry is deferred. Temporal history retention also limits server-side duplicate rejection, while persisted logical keys continue preventing repeated mock effects.

No Gemma, real notification provider, dashboard, approval execution, or n8n template is implemented. Next: explicit policies/approvals, a registered sandbox adapter, operation reconciliation/idempotency, and evidence-backed verification; only then place schema-validated Gemma proposals behind the policy gate. Revalidate unknown completion and actual worker interruption with sandbox evidence. Choose durable hosting and verify cost separately.
