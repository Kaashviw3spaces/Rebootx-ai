# Checkpoint 4 implementation report: n8n integration & end-to-end failure ingestion

## n8n integration validation — October 15, 2026

Delivered end-to-end integration between external n8n automation failures and the REBOOTX ingestion/recovery engine without weakening HMAC authentication or altering completed checkpoints.

### Delivered Components
- `integrations/n8n/workflows/primary_order_notification.json`: Exportable primary order notification workflow featuring Manual Trigger, Order Data Generator (`ORD-1042`, `notify-order-1042`), and an HTTP Request node targeting `/mock/primary-provider-failure` (simulating a provider 503 outage), with `settings.errorWorkflow` set to the REBOOTX error handler.
- `integrations/n8n/workflows/rebootx_error_handler.json`: Exportable error-handling workflow featuring an `Error Trigger` node, a `Code` node embedding the JavaScript formatting and signing logic, and an `HTTP Request` node POSTing exact raw JSON to `/api/v1/events/failure` with `X-Integration-ID` and `X-Webhook-Signature`.
- `integrations/n8n/code_nodes/format_and_sign_failure.js`: Standalone, zero-dependency JavaScript module. Uses native Node.js `crypto` if present, with seamless fallback to an embedded FIPS 180-4 pure JS HMAC-SHA256 implementation if the n8n execution environment blocks `require('crypto')` (`NODE_FUNCTION_ALLOW_BUILTIN` unset). Maps n8n error context to strict `FailureEvent` schema, sanitizes identifiers, and generates stable `event_id = "n8n:<execution_id>:<failed_step>"` ensuring deterministic deduplication across retries.
- `integrations/n8n/README.md`: Operator guide for native Windows setup (`npx.cmd n8n`, no Docker/WSL), workflow importing, environment variable configuration, and failure testing.
- `backend/scripts/simulate_n8n_failure.py`: CLI testing script executing the actual JavaScript formatter via Node.js and posting to the live API.
- `backend/tests/test_n8n_integration.py`: 13 comprehensive automated tests covering workflow JSON structure, HMAC parity against Python hashlib, Pydantic schema validation, stable deduplication, timestamp skew limits, missing metadata safety, tenant isolation, outbox claiming, Temporal activity state transitions (`RECEIVED` -> `RECOVERED`), and escalation (`NEEDS_ATTENTION`).

### Test Results
- **SQLite Regression Suite:** **170 passed, 5 skipped** in **10.99s** (baseline 157 passed -> 170 passed with 13 new Checkpoint 4 integration tests).
- **Native Temporal Integration:** **5 passed** in **68.70s** against Windows development server (`temporal.exe`).
- **Python Syntax:** `compileall` passed cleanly across `app/`, `scripts/`, `tests/`, and `integrations/`.
- **Git Diff:** `git diff --check` passed cleanly.

### Docker-Free Live n8n Demonstration Evidence
On October 15, 2026, a genuine live Docker-free end-to-end integration test was executed on native Windows using installed n8n `v2.43.6`, Uvicorn FastAPI, Temporal development server `v1.2.0`, REBOOTX recovery worker, and transactional outbox dispatcher.

1. **Primary Workflow Invocation:**
   - Webhook trigger endpoint `http://127.0.0.1:5678/webhook/order-notification` received an external POST request.
   - n8n Execution ID: `6` (Workflow `Primary Order Notification Dispatcher`, ID `fLkVQRkWnBPWIBG1`).
   - Downstream node `Call Primary Provider` attempted `POST http://127.0.0.1:8000/mock/primary-provider-failure` and failed with HTTP `503 Service Unavailable`.
2. **Error Trigger Activation:**
   - n8n caught the failure and activated `REBOOTX Error Handler` (Workflow ID `jfUNuHPdxg4WXlg9`) via its `Error Trigger` node.
   - The Code node ran `integrations/n8n/code_nodes/format_and_sign_failure.js` within n8n's sandbox, successfully mapping context and computing the HMAC-SHA256 signature using the embedded pure JS engine.
   - HTTP Request node POSTed exact signed JSON to `http://127.0.0.1:8000/api/v1/events/failure`.
3. **REBOOTX Ingestion & Deduplication:**
   - API responded with HTTP `202 Accepted` (`{"incident_id": "de18a744-3c93-4903-871c-6b3c115e18e2", "status": "RECEIVED", "duplicate": false}`).
   - Stable event ID: `n8n:6:Call Primary Provider`.
   - Tenant ID: `439d5f1b-d6a6-4abd-8511-f260edd53496`, Integration ID: `da9c3e2f-b9f4-416a-afdf-578b4e406901`.
   - Repeated delivery of the exact payload returned HTTP `202 Accepted` (`duplicate: true`, status `RECOVERED`). Database count invariants preserved: exactly 1 incident, 1 outbox record, 1 diagnosis record, 2 recovery attempt records.
4. **Temporal Recovery Orchestration:**
   - Outbox dispatcher claimed event and started Temporal workflow ID: `rebootx:recovery:v1:439d5f1b-d6a6-4abd-8511-f260edd53496:de18a744-3c93-4903-871c-6b3c115e18e2`.
   - State machine progressed: `RECEIVED` -> `VALIDATING` -> `DIAGNOSING` -> `PLANNED` -> `EXECUTING` (mock retry failed, fallback succeeded) -> `VERIFYING` -> `RECOVERED`.
   - Verification status: `MOCK_VERIFIED`.
   - Diagnosis provenance: `mock` (`mock-diagnosis-v1`, requested `gemma-4-26b-a4b-it`, policy reason `AI_POLICY_ACCEPTED`).

No database migrations were modified (database remains at revision `0003`). No live Neon operations or unauthorized Gemma calls occurred. External recovery actions remain strictly `mock-only-v1`. All background processes were cleanly terminated.

# Checkpoint 3 implementation report

## Neon PostgreSQL validation — October 14, 2026

Preflight verified the database URL came from the existing `backend/.env`, without an environment override or credential output. The configured endpoint is Neon, development configuration is active, libpq TLS is active, current database/role/schema match the configured target, and database/table ownership is verified. Opaque identity fingerprint: `16ce9cac7a93`. Initial public revision: **0002**. The exact Checkpoint 2 table/model baseline showed no unexpected drift or existing test schemas. All seven application tables were empty.

Reviewed `0001`, `0002`, `0003` and the pending PostgreSQL upgrade SQL. Applied only **0003**, creating the diagnosis table/index/constraints in a transaction. Existing tables were not dropped/reset/backfilled. Final public revision: **0003**. Diagnosis status/confidence checks, tenant/incident foreign key and uniqueness exist; model comparison found no drift. Existing row counts and content hashes were verified before migration, after migration and after all tests.

Validation results:

- **PostgreSQL: 157 passed, 5 skipped** in **1152.27 seconds**, using direct Neon connections and fresh randomly named isolated test schemas. The skipped native server cases were run separately.
- **SQLite: 157 passed, 5 skipped** in **11.10 seconds**, using disposable local databases.
- **Native Temporal: 5 passed** in **68.47 seconds**, using SQLite application persistence and mocked model transport; includes worker restart, replay and diagnosis idempotency.
- **Syntax: 52 Python files passed**; `git diff --check` passed. Existing deprecation warnings were non-failing.
- Added `tests/test_checkpoint3_persistence.py`: three cases verify deterministic, Gemma and mock source persistence; full diagnosis schema; linked incident/recovery/outbox/audit records; tenant-authorized reads; and committed-diagnosis idempotency. Gemma transport is mocked for PostgreSQL tests; no live inference was invoked.
- Existing PostgreSQL tests also verify tenant foreign-key rejection, outbox/attempt/audit idempotency, migration-model compatibility and preservation of nonempty synthetic historical records. Application code and migrations were not changed during this validation.

Final read-only verification: original public table counts/content hashes unchanged, public diagnosis table empty, **zero newly created test schemas remain**, revision `0003` current, no model drift. Cleanup removed only schemas created by the test fixtures. Because the preflight application tables contained zero rows, public preservation verifies that empty baseline; nonempty preservation was exercised separately with isolated synthetic PostgreSQL data.

Credential-safe evidence is retained under ignored `.temporal/neon-checkpoint3-{preflight,migration,final}.json`. No URLs/passwords/API keys are included. Actual application configuration and `AI_PROVIDER=mock` were unchanged. No live Gemma, external recovery, billing changes, commits or pushes occurred. Combined with the prior real Gemma schema/policy verification, **Checkpoint 3 is ready to commit for its defined advisory diagnosis and mock-recovery scope**. This is not production hosting, real recovery adapter or combined live-Gemma/Temporal/Neon end-to-end validation. Earlier unverified database statements below are historical and superseded by this validation.

## Successful real full-schema verification — October 14, 2026

The live full-schema gate is now verified. Exactly one official SDK request used the existing production prompt, `gemma-4-26b-a4b-it`, API `v1beta`, a 60-second timeout, 1,024 output-token budget, default thinking behavior and disabled SDK retries. Synthetic unfamiliar-response evidence was normalized to `UNKNOWN_FAILURE` with HTTP 200; the deterministic classifier returned no result, so the actual Gemma provider was called. No customer data or raw error message was sent.

- Latency: **21.622 seconds**; attempts: **1**; HTTP error: none.
- Candidates: **1**; finish reason: **STOP**; usable text: **yes**, **347 characters**.
- JSON parsing: **PASS**; all seven unchanged Pydantic fields: **PASS**; no repair or missing-field fabrication.
- Actual source: **gemma**. Category: **UNKNOWN_ERROR**; recommendation: **ESCALATE**; confidence: **0.1**.
- Deterministic policy evaluation: **PASS**, resulting in `AI_HUMAN_APPROVAL_REQUIRED` / `POLICY_REJECTED`. This is correct safe handling of ambiguous evidence, not an inference/schema failure. No action was authorized or executed.
- SDK usage metadata: **889 thought tokens**, **80 candidate tokens**. These are reported metadata, not proof of a general latency/token guarantee.
- Sanitized diagnostics are saved under ignored `.temporal/gemma-full-schema-verification.json`; raw response, prompt and credentials were neither printed nor stored there.

No application code changed or compatibility fix was needed. Regression tests were therefore not repeated; prior results remain **154 SQLite passes, 5 native Temporal passes**, with strict validation, timeout, policy, tenant isolation and idempotency coverage. This successful inference was tested separately from those mocked/native runs; it was not a live Temporal/PostgreSQL execution. Checkpoint 3's advisory diagnosis functionality is complete for its defined mock-recovery scope. Applying/reviewing persistent migration `0003`, live PostgreSQL validation, remote deployment and broader provider reliability remain separate work. No live Neon access, migrations, billing changes, external recovery, `.env` changes, commits or pushes occurred. The sections below retain historical failed probes and are superseded by this successful verification for the live-schema gate.

## Latency optimization — October 14, 2026

Added conservative structured fast-path classification inside the existing diagnosis service/activity. Gemma mode defaults to routing HTTP 429/401/503, known connection-timeout codes, and known schema-validation codes locally. Authentication/payload denials take priority over recoverable HTTP signals; unclear or inconsistent evidence routes to Gemma. Original mock mode remains unchanged. Every deterministic diagnosis validates against the full unchanged schema and passes the same policy; no confidence value expands permissions.

Actual source is stored using the existing provider column and exposed through API/audit metadata. Deterministic classification uses `deterministic-diagnosis-v1`, never a Gemma model ID. Hosted diagnosis uses Gemma; mock/fallback/failed output is explicitly mock, including historical source presentation. No schema migration or historical-data update is needed. External calls remain inside activities, workflow source is unchanged by this optimization, and committed result audits retain idempotency.

Prompt size for the same synthetic HTTP 429 input: **2,439 -> 2,183 characters**, a **10.5%** reduction including system instructions. Removed repeated evidence, absolute timestamps, empty history and duplicate contract instructions; preserved schema constraints/enums/required fields, meaningful attempt codes, input allowlisting, injection protections, concise JSON-only requirements and the synthetic example. Output budget is configurable 512–2048 tokens (default 1024). Optional documented Gemma 4 thinking levels are default/minimal/high; default omits the control. No Gemini-only settings are used and no new hosted latency improvement is claimed.

### Local benchmark (not hosted inference)

Command: `.venv/Scripts/python -B -m scripts.benchmark_diagnosis`. Each case: 100 warm-ups, 2,000 samples. Measures classification + output Pydantic + policy; excludes input construction, database, Temporal and network. The script refuses model routing and makes no SDK/network/DB calls.

| Structured case | Median ms | p95 ms |
|---|---:|---:|
| HTTP 429 | 0.0128 | 0.0170 |
| HTTP 401 | 0.0162 | 0.0251 |
| HTTP 503 | 0.0156 | 0.0246 |
| Connection timeout | 0.0190 | 0.0294 |
| Schema validation error | 0.0173 | 0.0254 |

These values are local compute timings, not model or endpoint speedups. Historical hosted compact/full latencies were 15.741/22.513 seconds; no new real Gemma inference was performed in this optimization. Full-schema hosted output remains unverified.

Final SQLite regression/AI tests: **154 passed, 5 skipped** in 8.93 seconds. Native Temporal tests: **5 passed** in 69.45 seconds. Added coverage for fast classification, ambiguous routing, confidence/approval denials, actual source persistence, historical fallback labels, injection resistance, output/thinking bounds, mixed native routing, replay, and committed-diagnosis redelivery (one mocked provider call for the ambiguous case, none for five structured cases). All prior recovery, provider failure/timeout, tenant isolation and migration compatibility tests remain covered. In-memory syntax: **51 files passed**; `git diff --check` passed. Native tests mock hosted transport; no actual hosted success is implied. Test subprocesses removed `TEST_DATABASE_URL`, forced SQLite/mock/empty keys, and used disposable ignored directories. No `.env` change, live Neon operations, external recovery, billing changes, commits or pushes. This latency optimization is locally validated; the full-schema live Gemma gate remains open.

## Output contract and timeout correction — October 14, 2026

The original parser grouped syntax, missing/type/enum/confidence/extra-field/formatting failures into `AI_INVALID_OUTPUT`. The earlier rejected full response was not retained, so its exact original validation defect remains unknown. Strict validation remains unchanged; failures now carry allowlisted internal `AI_OUTPUT_*` codes and known schema field names only. Details persist in existing result audits; no raw output, prompt, unexpected field names, input values or credentials are logged/stored. Provider envelope failures also distinguish missing/empty/oversized/token-limited text. Missing fields are never fabricated.

The prompt derives required fields, enums, types and bounds from the actual Pydantic schema, drops cosmetic titles, explicitly forbids Markdown/outside prose/extra keys, and includes one validated synthetic shape example. All seven required fields remain mandatory: failure_category, root_cause, explanation, recommended_action, confidence, requires_human_approval, alternative_actions. Input sanitization, redaction, injection protections, action allowlists, deterministic policy, fallback and tenant checks are retained. Optional explicit thinking control was removed to match the previous response-producing probe; its role in HTTP 500 is unproven.

AI timeout defaults to 60 seconds, bounded at 1–60. SDK retries remain disabled. New diagnosis activities use 75 seconds start-to-close / 240 seconds schedule-to-close for three deliveries. Other actions remain 30 / 120 seconds; workflow execution/run remains 20 minutes. Patch `diagnosis-timeouts-v1` preserves pre-patch replay budgets, and actual activity budget minus 10 seconds caps provider requests for legacy histories. Configuration never comes from environment inside workflow code. Longer waits/retries can increase elapsed time and quota consumption; 60 seconds is not a success guarantee.

After mocked tests passed, exactly one live synthetic HTTP 429 request used the updated production prompt/provider at 60 seconds. A response was received in **23.383 seconds** with no HTTP error, but the provider's text-presence/size guard rejected it before JSON parsing. Safe fallback was selected; no recovery action, database connection or Temporal execution occurred. This exposed a second classification gap in that guard, subsequently fixed and tested offline. Because the response was not retained, the exact missing/empty/oversized branch remains unknown. No second inference attempt was made. **Full Pydantic validation and policy evaluation of real Gemma output remain unverified.**

Final SQLite regression/AI tests: **125 passed, 4 skipped** in 19.15 seconds. Covers all previous cases plus granular rejection, prompt/schema consistency, timeout bounds/hierarchy, envelope failures, audited fallback and idempotency. Final native Temporal tests: **4 passed** in 59.22 seconds, including actual new-budget history replay, a captured pre-patch history replayed by current code, existing lifecycle cases and worker-process crash/restart. Real-server tests use mocked diagnosis transport; they do not prove live Gemma inference. In-memory syntax: **48 files passed**; `git diff --check` passed. Existing SQLite migration/model compatibility, historical-data preservation and offline additive PostgreSQL SQL tests passed; no live PostgreSQL operations were run. Deprecation warnings were non-failing.

All pytest subprocesses removed `TEST_DATABASE_URL`, forced local SQLite/default mock provider/empty API keys, and used fresh ignored `.temporal/` test directories. No `.env` changes, live Neon access/migrations, billing changes, external recovery actions, commits or pushes. Revisions `0001`/`0002` remain unchanged; no new migration was added for this correction. The earlier sections describe initial Checkpoint 3 implementation/history; this correction supersedes the earlier 20-second request budget. **Checkpoint 3 remains incomplete until a real response passes the full production schema and policy.**

## Delivered diagnosis architecture

Built on confirmed commit `308e198`, preserving Checkpoint 2. Added `app/ai/{schemas,prompts,gemma_client,policy,diagnosis}.py`, the package initializer, `app/services/diagnosis.py`, additive Alembic revision `0003_ai_diagnosis.py`, and AI unit/native Temporal tests. Updated settings/env placeholders, SDK requirements, incident/model/API schemas, activity/worker integration, development database checker, README, architecture, and execution plan. Existing `.env` was not overwritten. No commits or pushes were made.

The official Google Gen AI SDK 1.75.0 is installed in the existing virtual environment. Explicit Gemma model selection, fixed API endpoint, no tools, strict JSON/Pydantic validation, allowlisted sanitized evidence, and an independent policy gate constrain diagnosis. Inference is performed inside `recovery_step('diagnose')`, outside database transactions. Scope is revalidated before committing diagnosis/policy/state/result audit atomically. Workflow code and identifier-only Temporal schemas remain unchanged; all recovery actions/verification stay mock-only. Default mock mode and configurable deterministic fallback preserve existing behavior.

The authorized recovery GET exposes validated diagnosis, actual/requested model IDs, fallback reason and policy result. Timeline metadata includes fixed diagnosis status/model/policy codes; raw responses, prompts and credentials are omitted. Unsupported output, low confidence, human-review flags, and unsafe/unknown evidence cannot expand permissions. Human-review requirements escalate; there is no approval execution or real external adapter.

## Actual model availability and live boundary

On October 13, 2026, a credential-safe official SDK catalog request returned `models/gemma-4-26b-a4b-it` and `models/gemma-4-31b-it` for the configured key. The former is selected by default. [Google hosted Gemma docs](https://ai.google.dev/gemma/docs/core/gemma_on_gemini_api) and [pricing](https://ai.google.dev/gemini-api/docs/pricing) identify these hosted Gemma models and free-tier availability. No Gemini substitution or billing enablement occurred.

One bounded synthetic HTTP 429 diagnosis attempt failed with fixed `AI_UNAVAILABLE`; a bounded diagnostic retry confirmed provider HTTP 500. No raw provider messages or credentials were printed. Model catalog access is verified, **successful real inference is not**. The implemented fallback/escalation path safely handles this limitation. Routine tests never call live AI. No live Neon tests, migrations or external recovery actions were performed.

## Migration and limits

Revision `0003` creates `incident_diagnoses` with tenant/incident uniqueness, composite tenant scope, status/confidence constraints, structured diagnosis fields, model/provider, timestamp, fallback reason and deterministic policy result. `0001`/`0002` remain unchanged. SQLite migration tests verify model compatibility and preservation of Checkpoint 2 records; PostgreSQL upgrade SQL is generated in memory without connecting and checked for additive-only behavior. Persistent databases require a separately reviewed `0003` upgrade before deploying this code; no live upgrade is claimed.

Raw webhook error messages and customer context remain discarded. Optional `error.http_status` supplies numeric evidence; only fixed metadata/codes and timestamps are sent. Output prose filters are defense in depth, not a universal privacy detector. SDK timeout is capped at 20 seconds inside the existing 30-second activity limit. No SDK retry is enabled; Temporal keeps bounded delivery retries. A pre-commit crash/concurrent delivery may repeat inference, while a committed diagnosis result prevents another request on redelivery. One persisted diagnosis and idempotent mock effects are guaranteed by existing locks/audit keys plus new uniqueness; exactly-once provider requests are not claimed. Real inference, live PostgreSQL, remote hosting and server-restart durability remain unverified in this checkpoint.

## Checkpoint 3 validation results

- Final SQLite regression/AI suite: **90 passed, 3 skipped** in 7.59 seconds. Includes all 41 existing Checkpoint 1/2 cases and 49 new AI cases. The three native Temporal tests are intentionally skipped in this run.
- Final real native Temporal suite: **3 passed** in 55.63 seconds. Existing lifecycle/retry/duplicate-start/replay and actual worker-process crash/restart passed. The added test covers five validated AI policy scenarios with mocked Gemma transport, diagnosis acknowledgement loss after commit, no repeated inference on redelivery, deterministic replay, and rejection of a fallback without permission before any fallback attempt is created.
- Verified malformed/missing/extra/duplicate JSON, invalid categories/actions/types/confidence, low confidence, human-review denial, provider timeout/authentication/rate limiting/unavailability, injection-resistant evidence, output/key filtering, tenant API and database isolation, revocation during inference, persisted results, explicit fallback enabled/disabled, and regression behavior.
- SQLite Alembic model drift/history-preservation checks and in-memory additive PostgreSQL SQL generation passed. No live PostgreSQL validation was run.
- In-memory Python syntax checks: **47 files passed**. `pip check`: **No broken requirements found**. `git diff --check`: passed. Existing Starlette/httpx and SDK/Python deprecation warnings were non-failing.
- Every pytest subprocess removed `TEST_DATABASE_URL`, forced `DATABASE_URL=sqlite:///:memory:`, `AI_PROVIDER=mock`, an empty Gemini API key, and fresh UUID-named base directories under ignored `.temporal/`. Native runs explicitly used the installed CLI and enabled only local integration tests; Gemma responses stayed mocked.
- Commands: `.venv/Scripts/python -B -m pytest -q -p no:cacheprovider --basetemp <fresh-directory>`; separately `.venv/Scripts/python -B -m pytest -q tests/test_temporal_integration.py tests/test_ai_temporal.py -p no:cacheprovider --basetemp <fresh-directory>`. Required environment isolation and reproduction commands are in README.
- Implementation is locally verified and reviewable; Checkpoint 3's successful real-inference gate remains **blocked by provider HTTP 500**, and live `0003` deployment remains unapplied/unverified. Do not claim an end-to-end live Gemma/PostgreSQL integration based on these tests.

# Checkpoint 2 implementation report (historical)

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
