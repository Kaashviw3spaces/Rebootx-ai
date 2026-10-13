# REBOOTX — Product Requirements Document

**Version:** 0.1 | **Date:** 2026-10-13 | **Status:** Hackathon MVP specification

## 1. Product thesis
**REBOOTX** is a multi-tenant recovery service for existing automations. A customer connects a supported workflow, configures allowed recovery actions, and sends authenticated failure events. REBOOTX diagnoses the failed business operation, executes approved recovery strategies in a bounded sequence, verifies the outcome, and escalates when it cannot safely finish the job.

**Tagline:** *Your automation fails. REBOOTX takes over.*

This MVP **does not** claim to repair arbitrary automation logic, take over every workflow, or rewrite an n8n execution's status. It recovers a supported failed *business operation* through pre-integrated actions.

## 2. Audience and value
- **Primary users:** automation freelancers, small agencies, small businesses operating n8n workflows.
- **Problem:** a single external API failure can leave an otherwise successful business process unfinished; diagnosing and manually retrying costs time.
- **Value proposition:** faster, auditable, policy-constrained recovery with fewer manual interventions.
- **Monetization hypothesis:** monthly fee based on connected workflows and recovery runs. Pricing is unvalidated; user interviews required.

## 3. MVP scope (must ship)
1. **Two isolated demo tenants** with tenant-scoped workflow registration, credentials, policies, and incident views.
2. **One real n8n integration** via an n8n error workflow that POSTs a failure event to our authenticated webhook.
3. **One recoverable workflow type:** customer notification delivery. An n8n workflow attempts to send an email/notification using a primary provider; on failure, REBOOTX retries safely or uses an explicitly configured backup adapter.
4. **Gemma-based structured diagnosis** producing a constrained JSON plan, validated against a schema. Rule-based fallback if model unavailable.
5. **Temporal recovery orchestration** with bounded retries, backoff, alternative strategy, verification, and escalation.
6. **Human escalation:** dashboard incident details and an approval/request-input state for unsupported or risky actions.
7. **Incident dashboard:** status, timeline, attempted strategies, evidence, and tenant-level metrics.
8. **Auditable demo:** reproducible injected provider outage; evidence that an external n8n failure triggers recovery, not a dashboard-only simulation.
9. **Partner features:** ElevenLabs generates an optional spoken incident brief; SerpApi retrieves relevant documentation on demand and clearly labels it as advisory, never executable instructions; deployment on Render.

## 4. Non-goals
- Universal Zapier/Make/Python connectors; automated arbitrary code repair; free-form agent browser actions; unattended credential rotation; financial transactions; guaranteed delivery or exactly-once external execution; production-grade compliance certification.
- Automatically switching *all new* executions from a failed platform; the MVP recovers **individual failed operations** only.

## 5. User journeys
### Connect
User signs in → creates workspace → registers `notification_v1` workflow → receives scoped webhook token → imports n8n error-workflow template → configures primary/backup provider adapters and retry/approval policy → sends test event.

### Recover
n8n step fails → error workflow posts event + operation reference → API authenticates and deduplicates → Temporal starts recovery → system checks operation state → Gemma proposes from allowed actions → policy engine approves/rejects → execute retry/fallback → verify provider acceptance → mark `RECOVERED` or escalate.

### Escalate
Unknown failure / exhausted attempts / ambiguous completion → `NEEDS_ATTENTION` → user sees cause, attempts, recommended next step, and approval controls → human can retry an allowed action or close incident.

## 6. Functional requirements
| ID | Requirement | Acceptance condition |
|---|---|---|
| FR-01 | Authenticated failure ingestion | Invalid token rejected; event linked to token's tenant, not request-supplied tenant |
| FR-02 | Event deduplication | Same `(tenant_id, source, execution_id, failed_step)` does not create duplicate active recovery |
| FR-03 | Schema-validated AI plan | Only enumerated action types and registered adapters accepted |
| FR-04 | Bounded execution | Configurable max attempts and deadline enforced |
| FR-05 | Outcome verification | Provider acceptance ID or explicit verified state required for `RECOVERED` |
| FR-06 | Ambiguous outcome handling | Timeout after possible success → reconcile before retry; otherwise escalate |
| FR-07 | Tenant isolation | Tenant A cannot query or act on tenant B's workflows/incidents |
| FR-08 | Incident audit trail | Timestamps, actions, decisions, errors, verification, redacted payload references |
| FR-09 | Human escalation | Unsafe/unavailable strategy produces actionable incident state |
| FR-10 | External integration | Actual n8n error event produces incident and recovery execution |
| FR-11 | Optional voice briefing | ElevenLabs output only after incident summary is redacted and approved for speech |
| FR-12 | Optional documentation research | SerpApi source URLs displayed as references; retrieved text cannot grant new permissions |

## 7. Non-functional requirements
- **Security:** server-side secret storage, TLS, least-privilege integration credentials, redaction of PII/tokens in model prompts/logs, webhook auth, rate limits, audit logs.
- **Reliability:** Temporal retry semantics, durable state, provider idempotency keys, reconciliation, bounded execution.
- **Privacy:** isolate tenant records and prompts; use synthetic demo data; document any external model/API data flows.
- **Observability:** trace each incident across webhook → Temporal → adapter → verification; record failures without secrets.
- **Cost:** free-tier-first, with local Temporal development; verify current Render/Temporal/Gemma availability and quotas before committing to deployment.

## 8. Success metrics
- Demo: two distinct tenants; one real n8n error webhook; one primary-provider failure recovered via fallback; one unrecoverable incident escalated; duplicate event handled safely.
- Measure **detection latency**, **time to recovery**, **recovered / attempted operations**, **manual intervention rate**, **duplicate side effects**, and **false recovery declarations**.
- No invented accuracy or recovery percentages: report measured results only.

## 9. Acceptance test scenarios
1. Primary notification provider returns 503 → fallback provider accepts message → incident `RECOVERED` with provider ID.
2. Transient timeout, provider confirms *not delivered* → bounded retry succeeds.
3. Provider timeout with unknown completion → query status; if unverifiable, escalate (do **not** blindly resend).
4. All permitted providers fail → `NEEDS_ATTENTION` with attempt history.
5. Malformed Gemma plan / prompt injection in error text → reject plan; deterministic safe fallback.
6. Duplicate webhook delivery → same incident, no duplicate notification.
7. Tenant A token used for tenant B resource → denied.
8. Worker restart mid-recovery → Temporal resumes without repeated confirmed side effects.

## 10. Open questions / decisions to validate
- Specific primary/backup notification adapters and test-mode credentials.
- Gemma execution route: local/open-weight inference or hosted API; confirm license, model version, compute, and free-tier availability.
- Temporal deployment: local/self-hosted for development; hosted option and persistence for public demo.
- Authentication approach for demo users and data-retention policy.
