# REBOOTX — Technical Architecture

**Version:** 0.1 | **Date:** 2026-10-13

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
       └── Temporal client ── start RecoveryWorkflow(incident_id)
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

Tenant identity is derived from authenticated token; never from JSON. Resolve `recipient_ref` via a tenant-scoped lookup. Avoid raw personal data in error payloads and LLM prompts. Webhook response is `202 Accepted` after durable incident persistence and workflow start; repeat delivery returns the existing incident ID.

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
- **Local:** Docker Compose for Postgres and Temporal dev server; FastAPI and worker processes; React dev server; local/mock Gemma where necessary.
- **Public demo:** Render for dashboard/API and suitable worker runtime. Temporal server requires durable infrastructure; verify feasible hosting before committing. If Temporal cannot be deployed publicly within budget, document and show a reproducible local Temporal-backed demo while hosting the dashboard/API publicly—do not imply public recovery is live when it isn't.
- Database migrations and secret configuration required before enabling external tenants.

## 10. Verification semantics
Provider returning `202` means **accepted for processing**, not necessarily delivered to recipient. UI must say `ACCEPTED_BY_PROVIDER` unless delivery receipt is available. A `RECOVERED` incident means the configured business-operation completion criterion is met (e.g. accepted by provider); explicitly label this criterion.
