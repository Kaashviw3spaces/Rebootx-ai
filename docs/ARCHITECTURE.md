# REBOOTX — Technical Architecture

**Version:** 0.2 | **Date:** 2026-10-15

**Implemented through Checkpoint 4:** FastAPI HMAC ingestion, Neon persistence, transactional outbox, Temporal `IncidentRecoveryWorkflow`, Gemma 4 advisory diagnosis, n8n Error Trigger integration, exact-byte HMAC formatting node, and end-to-end failure ingestion. Real external recovery actions and frontend dashboard remain future work.

## 1. Architecture at a glance

```text
Customer n8n instance
  └─ Error workflow (authenticated failure webhook)
       │
       ▼
Render-hosted FastAPI Ingestion API ── auth, rate limit, validation, dedup
       │
       ├── PostgreSQL ── tenants, workflows, policies, incidents, audit, secrets refs
       │
       └── Transactional recovery outbox ── dispatcher ── Temporal
                                  │
                                  ▼
                         Temporal worker (Python)
                           ├─ load context / reconcile prior outcome
                           ├─ Gemma diagnosis (structured proposal)
                           ├─ deterministic policy gate
                           ├─ approved recovery adapters
                           ├─ verify provider outcome
                           ├─ retry / alternate / escalate
                           └─ persist audit events
                                  │
                 ┌────────────────┴────────────────┐
                 ▼                                 ▼
           React dashboard                   Optional services
        incident + approval UI          ElevenLabs spoken briefing
                                         SerpApi docs discovery
```

**Key distinction:** n8n continues to own its original automation. REBOOTX can complete a **registered failed operation**, not transparently resume arbitrary internal n8n nodes or change the failed execution record.

## 2. Repository layout
```text
rebootx/
  apps/web/                 # React + TypeScript dashboard
  services/api/             # FastAPI ingestion, auth, incident endpoints
  services/worker/          # Temporal worker + workflow definitions
  packages/contracts/       # shared JSON schemas / generated types
  packages/adapters/        # primary + backup notification providers
  integrations/n8n/         # exportable n8n demo workflow + error workflow
  infra/                    # local compose, Render config, env examples
  tests/                    # unit, integration, e2e, failure injection
  docs/                     # PRD, architecture, execution, demo
```

## 3. Core data model
- `tenants(id, name, created_at)`
- `users(id, tenant_id, role, auth_subject)`
- `integrations(id, tenant_id, kind, secret_ref, enabled)`
- `workflows(id, tenant_id, external_id, kind, policy_id, enabled)`
- `policies(id, tenant_id, max_attempts, max_duration_s, allowed_actions, allowed_adapters, approval_rules)`
- `incidents(id, tenant_id, workflow_id, source, source_execution_id, failed_step, operation_id, status, created_at, resolved_at)`
- `attempts(id, tenant_id, incident_id, action, adapter, outcome, external_reference, started_at, ended_at)`
- `audit_events(id, tenant_id, incident_id, actor, event_type, redacted_details, occurred_at)`
- `operation_outcomes(tenant_id, operation_id, adapter, idempotency_key, status, external_reference)`

All DB reads/writes are tenant-scoped. Use DB constraints on `(tenant_id, source, source_execution_id, failed_step)` and unique idempotency keys. Never store plaintext credentials in audit events.

## 4. Failure webhook contract
Example **illustrative** request; n8n error-workflow fields must be mapped into this schema by our template.

```http
POST /v1/events/failure
Authorization: Bearer <workflow-scoped-token>
Content-Type: application/json
```

```json
{
  "schema_version": "1.0",
  "source": "n8n",
  "source_execution_id": "exec-1042",
  "workflow_external_id": "notify-orders",
  "failed_step": "send_customer_confirmation",
  "operation_id": "notify-order-1042",
  "error": {"category": "PROVIDER_UNAVAILABLE", "message": "HTTP 503"},
  "context": {"recipient_ref": "customer-27", "template_id": "order-confirmation", "order_ref": "order-1042"}
}
```

Tenant identity is derived from authenticated credentials; never from JSON. Resolve `recipient_ref` via a tenant-scoped lookup when that feature is implemented. Avoid raw personal data in error payloads and LLM prompts. In Checkpoint 2, `202 Accepted` follows the atomic incident, audit, and recovery-outbox commit. An independent dispatcher starts Temporal; database commit and workflow start are not atomic. Repeat delivery returns the existing incident ID without creating another outbox row. The deployed endpoint remains `/api/v1/events/failure` with exact-byte HMAC authentication; the bearer example above is illustrative, not the current contract.

## 5. Recovery state machine
```text
RECEIVED → VALIDATING → DIAGNOSING → PLANNED → EXECUTING → VERIFYING
                │           │          │            │            │
                └───────────┴──────────┴────────────┴────────────┤
                                                                 ▼
                                                      RECOVERED | NEEDS_ATTENTION
```

### Workflow pseudocode
```python
async def recovery_workflow(incident_id):
    incident = await load_incident(incident_id)
    if await operation_already_completed(incident.operation_id):
        return await mark_recovered_from_evidence(incident)
    plan = await diagnose_with_gemma(incident)  # structured JSON; untrusted
    candidates = validate_and_rank_against_policy(plan, incident.policy)
    for candidate in candidates[:incident.policy.max_attempts]:
        if deadline_exceeded() or requires_ungranted_approval(candidate):
            break
        if await operation_already_completed(incident.operation_id):
            return await mark_recovered_from_evidence(incident)
        outcome = await execute_adapter_with_idempotency(candidate)
        verified = await verify_or_reconcile(outcome)
        if verified == 'SUCCESS':
            return await mark_recovered(incident, outcome.external_reference)
        if verified == 'UNKNOWN':
            break  # avoid duplicate side effects
    return await escalate_with_evidence(incident)
```

Use Temporal activities for network calls, model inference, and DB operations. Keep workflow code deterministic; do not make direct HTTP/model calls from Temporal workflow code. Temporal activity retries must align with business-level attempt limits and idempotency.

## 6. Recovery action registry
| Action | Description | Preconditions |
|---|---|---|
| `RETRY_SAME_PROVIDER` | Retry transient failure | Status reconciled; retryable error; remaining budget |
| `USE_BACKUP_PROVIDER` | Send through registered backup adapter | Backup enabled; authorized; dedup status known |
| `TRANSFORM_VALIDATED_PAYLOAD` | Apply registered schema transform | Validated mapping; no arbitrary code generation |
| `REQUEST_APPROVAL` | Wait for human | Action needs permission or data |
| `ESCALATE` | Stop automatic attempts | Unknown outcome, exhausted budget, auth error |

**No arbitrary shell execution, arbitrary URL POST, unrestricted browsing, or generated code execution.** LLM output is an advisory plan, never authorization.

## 7. AI, search, and voice boundaries
- **Gemma:** supply redacted error class, allowed actions, adapter metadata, and minimal workflow context. Require JSON with `diagnosis`, `confidence`, `candidate_actions`, `rationale`, `evidence_refs`; schema-validate and cap length. On timeout or invalid JSON, use safe deterministic rules.
- **SerpApi:** optional docs lookup to support diagnosis or show cited sources in dashboard; treat results as untrusted data, not tool commands. Not required for the critical path.
- **ElevenLabs:** optional generated spoken summary after redaction. Failure must never block recovery.

## 8. Multi-tenant security
- Authenticate users; use signed/scoped webhook tokens with rotation and revocation.
- Tenant isolation in every query, integration credential, Temporal workflow ID, and adapter invocation; test cross-tenant denial.
- Encrypt credentials at rest with a secrets manager or envelope encryption; never ship credentials to the browser.
- Restrict outbound destinations via adapter allowlists; enforce per-tenant rate and spending limits.
- Record immutable-style append-only audit entries; sanitize logs; protect against replay and duplicate events.
- Separate test and production integrations; use synthetic customer data for public demos.

## 9. Hosting and development
- **Local Windows:** Neon PostgreSQL, native Temporal CLI development server, and separate FastAPI, outbox dispatcher, and worker processes. Docker and WSL are unnecessary. Start Temporal with `--db-filename` to retain local server state. React and Gemma remain future work at Checkpoint 2.
- **Public demo:** Render for dashboard/API and suitable worker runtime. Temporal server requires durable infrastructure; verify feasible hosting before committing. If Temporal cannot be deployed publicly within budget, document and show a reproducible local Temporal-backed demo while hosting the dashboard/API publicly—do not imply public recovery is live when it isn't.
- Database migrations and secret configuration required before enabling external tenants.

## 10. Verification semantics
Provider returning `202` means **accepted for processing**, not necessarily delivered to recipient. UI must say `ACCEPTED_BY_PROVIDER` unless delivery receipt is available. A `RECOVERED` incident means the configured business-operation completion criterion is met (e.g. accepted by provider); explicitly label this criterion.

## 11. Checkpoint 2 implemented orchestration

This section records the inherited Checkpoint 2 behavior. Section 12 extends diagnosis with Gemma; recovery execution remains mock-only.

```text
HMAC webhook -> one PostgreSQL transaction:
                  incident + INCIDENT_RECEIVED audit + recovery_outbox
               -> 202 (durably queued)

Independent dispatcher -> claim with lease -> commit claim
                       -> start IncidentRecoveryWorkflow with tenant/incident ID
                       -> lease-fenced acknowledgement or delayed retry

Temporal worker -> deterministic workflow -> transactional activities:
                  VALIDATING -> DIAGNOSING -> PLANNED -> EXECUTING
                  -> VERIFYING -> RECOVERED / NEEDS_ATTENTION
```

`recovery_outbox` is unique per `(tenant_id, incident_id)`, references the same-tenant incident, and stores a deterministic Temporal ID, timestamps, lease token, dispatch count, and fixed error code. It contains no credentials or raw webhook payload. PostgreSQL claims use `FOR UPDATE SKIP LOCKED`. No database transaction spans a Temporal RPC. A crash after start but before acknowledgement is safe: the row becomes reclaimable, and `REJECT_DUPLICATE` / already-started handling converges on the existing execution. Dispatch retries back off to at most 60 seconds. Stop/restart the dispatcher freely; do not change namespaces during pending dispatch.

Revision `0002` adds the outbox, incident recovery/verification fields, and nullable logical keys with same-tenant uniqueness on `recovery_attempts` and `audit_logs`. It preserves old rows and does not automatically launch historical incidents. PostgreSQL performs additive alterations in place; SQLite batch alteration is used only for compatibility with disposable local test databases. The live database is never downgraded or truncated.

Activity writes lock the same-tenant incident row and verify its registered workflow/integration and enabled flags. Unique logical keys plus transactional audit results make activity redelivery idempotent, including a lost acknowledgement after commit. Old steps return their original result without overwriting later state. SQLite reserves a write transaction because it has no row locks. Revoked scope fails closed. Ingestion still rejects caller-supplied tenant IDs; the existing hashed tenant read credential authorizes all incident/attempt/timeline endpoints.

Only fixed mock fixtures classify network/rate-limit/authentication/payload/unknown failures. Recoverable fixtures allow one mock retry, then one mock fallback, followed by verification. Rate-limit delay uses a deterministic two-second Temporal timer. Unsafe/unknown fixtures escalate without retry. No activity calls an external automation, provider, AI model, or customer-system API. `MOCK_VERIFIED` is synthetic evidence, never provider delivery. Retry delivery limits (three), activity timeouts (30 seconds/two minutes), and workflow deadline (20 minutes) are explicit.

Native Windows CLI 1.9.1 / server 1.32.0 worked through SDK 1.34.0 `WorkflowEnvironment.start_local()` with an existing executable. Real test-server execution, activity retry after lost acknowledgement, duplicate start, history replay, and actual worker-process crash/restart are covered separately from mocked tests. Worker crash/restart was tested with both SQLite and isolated live Neon application persistence. The tested server remained running during worker restart; server-restart durability and production hosting are not claimed. Remote TLS/API-key configuration is supported but has not been validated against a configured remote server. Continuing database outages, workflow deadline expiry, and revoked scope require operator reconciliation.

See `backend/README.md` for Docker-free installation, migration, worker/dispatcher startup, environment settings, and test commands.

## 12. Checkpoint 3 advisory Gemma diagnosis

Current database gate: verified the configured Neon development database identity/ownership, TLS and drift-free revision `0002`, then applied only additive `0003`. Final model/constraint checks passed at `0003`. PostgreSQL tests (157 passes) use isolated synthetic schemas and mocked model transport to verify source provenance, tenant isolation, links and idempotency; SQLite tests also pass (157), and native Temporal tests pass separately (5). Final readback confirmed unchanged empty application-table counts/content hashes, zero public diagnosis rows and no remaining test schemas. Nonempty historical preservation was exercised in isolated PostgreSQL data. No live inference or external recovery occurred during database validation. This establishes development persistence, not combined live-Gemma/Temporal/Neon end-to-end or production hosting reliability; earlier database-unverified statements below are historical.

Current live-schema gate: on October 14 one ambiguous synthetic request actually called Gemma (fast path returned no classification). A single `STOP` candidate returned in 21.622 seconds; 347 characters parsed/validated all seven required fields. `UNKNOWN_ERROR` / `ESCALATE`, confidence 0.1, entered the unchanged policy and required human approval. This verifies actual inference, strict schema and safe denial with the production prompt/settings, separately from mocked transport/native orchestration tests. No real recovery or database operation occurred. Earlier unverified/failed-probe statements below are historical; live PostgreSQL, remote deployment and general reliability remain unverified.

Latency routing extension: in explicit Gemma mode, fixed structured HTTP 429/401/503 and known connection/schema-error codes first enter a local classifier. Authentication/payload signals take denial precedence; ambiguous evidence calls Gemma. Both outputs validate against the same schema and enter the same policy, then follow the existing revalidated atomic persistence path. Source is stored in the existing provider column and included in authorized API/audit metadata (`deterministic`, `gemma`, `mock`); deterministic output is never attributed to Gemma. No new migration, workflow command or external recovery action is introduced. Result audits prevent repeated diagnosis after commit. Request prompt removes duplicate evidence/time/empty history, while full constraints remain. Output-token limits are bounded; documented optional Gemma thinking controls are unset by default (provider default behavior, not a claim that thinking is disabled). Local classifier benchmarks exclude database/Temporal/network; hosted latency and full-schema live success are not inferred from them.

October 14 correction: strict output validation now yields fixed syntax/format/missing/type/enum/confidence/extra-key/envelope codes and allowlisted field names in existing audit metadata. Raw responses and unexpected field names are never stored. The prompt uses the actual schema and a synthetic example; all seven fields remain mandatory, with no repair/default filling. AI requests default to 60 seconds (bounded 1–60), and actual activity headroom can cap this for legacy histories. Diagnosis alone receives versioned 75/240-second start/total budgets; other actions remain 30/120 seconds, delivery retries remain three, and the workflow deadline remains 20 minutes. `workflow.patched('diagnosis-timeouts-v1')` protects old-history replay. SDK retries and tools remain disabled; explicit optional thinking control is omitted. A real production probe returned in 23.383 seconds but was rejected before parsing by the provider envelope guard. Its exact envelope branch was not retained; the guard is now separately classified/tested offline. Full-schema live inference remains unverified; no live PostgreSQL operations or external recovery actions occurred.

```text
Existing webhook transaction -> incident + audit + durable outbox
Existing deterministic workflow -> recovery_step('diagnose') activity
  scoped sanitized evidence read -> close transaction
  Google Gen AI SDK / Gemma -> strict JSON/Pydantic validation
  deterministic evidence/action/confidence/human-review policy
  revalidate tenant and enabled registration -> lock incident
  one transaction: diagnosis + policy + state + result audit
Existing workflow -> permitted mock retry/fallback -> mock verification/escalation
Tenant-authorized recovery GET -> structured diagnosis + recovery outcome
```

Provider inference occurs only in the activity. Workflow business flow and Temporal payload schemas remain intact; diagnosis timeout commands now use the replay-safe patch described above. Payload/history contains fixed identifiers/codes; model prose and API keys remain outside Temporal history. Revision `0003` adds a diagnosis table unique per tenant/incident with composite same-tenant foreign keys; `0001`/`0002` remain unchanged. No historical backfill or live Neon upgrade was run.

The worker defaults to mock mode; explicit `AI_PROVIDER=gemma` selects only a verified Gemma model. Both `gemma-4-26b-a4b-it` and `gemma-4-31b-it` were returned by the configured key's catalog; default selection is the former. A bounded generation attempt and diagnostic retry failed, with HTTP 500 confirmed on retry. Catalog access is verified; real inference is not. No other model/provider is substituted.

Inputs exclude raw error text/customer context and tenant/execution/external workflow identifiers. Only fixed failure/integration/workflow/attempt codes, timestamp, and optional numeric HTTP status leave the service. Output has closed category/action enums, bounded text, strict types, confidence range, and extra-field rejection. Duplicate keys, markdown, suspicious prose, and key echo are rejected. No tools are configured. The request targets the official API with an explicit private key; endpoint/proxy environment overrides are disabled.

Model confidence is advisory. Deterministic policy independently rejects unsafe evidence, unsupported categories, low confidence, and human-review requirements. Human approval is a denial/escalation gate, not an execution feature. Approved fallback remains the existing mock adapter. Invalid output/provider failures persist fixed reason codes and either use legacy deterministic fixtures (`FALLBACK`) or escalate (`FAILED`) depending on configuration. Valid denied output is `POLICY_REJECTED`; successful accepted output is `SUCCEEDED`; explicit mock mode is `MOCK`.

Scope is checked before and after the provider call. No database transaction spans inference. Committed result audits deduplicate activity redelivery; a pre-commit crash or parallel delivery can repeat inference, but locks/unique constraints prevent duplicate persisted diagnoses and recovery effects. AI request timeout is configurable up to 60 seconds within the new 75-second diagnosis activity budget and capped by actual activity headroom for legacy histories. SDK retries are disabled and Temporal delivery retries remain bounded. Continuing database outages, revoked scope, workflow timeouts, and operator reconciliation remain existing limitations.

Tests distinguish mocked model transport, real native Temporal orchestration (including lost diagnosis acknowledgement, replay and worker restart), actual inference, and live PostgreSQL. Only the first two are verified in Checkpoint 3. No external recovery actions are enabled. See backend README and implementation report for exact settings/results and provider limitations.
 
+## 13. Checkpoint 4 n8n Integration & Failure Ingestion
+
+Checkpoint 4 connects customer n8n workflow failures to the REBOOTX ingestion API and Temporal recovery orchestrator without weakening the zero-trust exact-byte HMAC authentication contract.
+
+```text
+Customer n8n Instance
+  ├─ Primary Order Workflow -> calls external API -> receives HTTP 503 / timeout
+  │    └─ Workflow Setting: errorWorkflow -> 'REBOOTX Error Handler'
+  │
+  └─ REBOOTX Error Handler Workflow
+       ├─ Error Trigger: intercepts execution failure metadata
+       ├─ Format & Sign Code Node:
+       │    ├─ maps to strict FailureEvent schema
+       │    ├─ derives stable event_id = 'n8n:<exec_id>:<step>' (deterministic deduplication)
+       │    ├─ normalizes error category and HTTP status
+       │    ├─ checks native Node.js 'crypto' module
+       │    ├─ falls back to pure JS FIPS 180-4 HMAC-SHA256 if sandbox restricts built-ins
+       │    └─ outputs raw JSON string + X-Webhook-Signature
+       └─ HTTP Request Node: POST /api/v1/events/failure
+```
+
+### Key Invariants
+- **Deduplication:** Event identifiers are deterministic (`n8n:<exec_id>:<failed_step>`). Retrying the same failed execution yields the identical `event_id`, triggering REBOOTX database constraints and returning `duplicate: true` without creating redundant incidents or Temporal outbox rows.
+- **Environment Independence:** The formatter script operates seamlessly both when Node.js `crypto` is accessible and within restricted n8n Code node sandboxes where `NODE_FUNCTION_ALLOW_BUILTIN` is unset.
+- **Mock Scope:** External recovery actions remain mock-only (`mock-only-v1`); no live notification providers or external APIs are invoked.
+
