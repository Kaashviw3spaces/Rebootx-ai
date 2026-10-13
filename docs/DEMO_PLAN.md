# REBOOTX — Demo & Evaluation Plan

**Version:** 0.1 | **Date:** 2026-10-13

## Demo promise
Demonstrate that **an external n8n automation failure can trigger safe, bounded recovery of a registered business operation**, with visible evidence, rather than pretending to restart or rewrite arbitrary n8n workflows.

## Setup
- Tenant A: `Acme Demo Store`; Tenant B: `Northstar Demo Studio` (synthetic).
- n8n workflow: `New Test Order → Format Confirmation → Primary Notification Adapter`.
- n8n error workflow: capture error + stable `operation_id` → POST authenticated event to REBOOTX.
- REBOOTX: FastAPI + DB + Temporal worker + Gemma + approved primary/backup adapters + dashboard.
- Use sandbox or synthetic recipients. Do not send unsolicited messages to real users.
- Failure injection toggle: primary provider returns controlled 503/timeout; backup returns provider acceptance ID.

## 90-second judge demo storyboard
| Time | Screen/action | Proof |
|---|---|---|
| 0–10s | Show n8n workflow and connected REBOOTX workspace | Real external integration |
| 10–20s | Trigger test order; primary provider fails | Visible n8n error event |
| 20–35s | REBOOTX receives event; incident opens | Authenticated webhook and incident ID |
| 35–50s | Gemma suggests permitted recovery; policy validates | AI recommendation distinct from action authorization |
| 50–65s | Temporal executes backup adapter and verifies acceptance | Recovery action + external reference |
| 65–75s | Dashboard shows `RECOVERED`, attempt history, duration | Auditable outcome |
| 75–85s | Replay identical webhook; no second send | Idempotency evidence |
| 85–90s | Show escalation example and one-sentence value | Safe failure boundary |

Use prerecorded video if live external services are unreliable, but label recording and show repository/tests for reproducibility.

## Scenario matrix
| ID | Failure | Expected behavior | Evidence |
|---|---|---|---|
| S1 | Primary provider 503 | Use permitted backup, verify acceptance | Incident + adapter request ID |
| S2 | Transient retryable error | Retry within budget, then verify | Attempt count/timestamps |
| S3 | Both providers unavailable | Escalate; no success claim | `NEEDS_ATTENTION` timeline |
| S4 | Duplicate n8n event | Same incident; no duplicate side effect | DB constraint + send count |
| S5 | Ambiguous timeout after possible send | Reconcile or escalate; no blind resend | Provider status check |
| S6 | Gemma invalid plan / injection | Reject; safe rule fallback | Validation log |
| S7 | Cross-tenant request | Access denied | API test |
| S8 | Temporal worker restart | Resume durable workflow; no repeated confirmed send | Worker log + adapter counter |
| S9 | Optional SerpApi unavailable | Recovery continues without web lookup | Incident still completes |
| S10 | Optional ElevenLabs unavailable | Recovery continues without voice | Incident still completes |

## Metrics to collect
- `detection_latency_ms`: original failure timestamp to accepted webhook.
- `recovery_latency_ms`: incident created to configured completion criterion.
- `recovery_rate`: verified recovered / attempted supported operations.
- `manual_intervention_rate`: escalated / attempted operations.
- `duplicate_side_effect_count`: verified repeated sends for one operation ID.
- `plan_rejection_count`: model plans rejected by policy/schema.

Collect at least 10 synthetic runs across scenarios, report sample size and failures. Do not infer production reliability from hackathon tests.

## Evidence checklist
- [ ] n8n workflow and error-workflow screenshots.
- [ ] Webhook request/response with secrets redacted.
- [ ] Temporal workflow history / trace.
- [ ] Gemma structured recommendation + policy decision.
- [ ] Provider acceptance evidence; label acceptance vs final delivery accurately.
- [ ] Incident timeline and tenant separation.
- [ ] Tests for duplicate event, unknown outcome, and escalation.
- [ ] ElevenLabs sample and SerpApi sourced documentation view (if built).
- [ ] Public repo, installation instructions, live/demo limitations.
- [ ] First-user feedback with consent, distinguishing feedback from measured metrics.

## DEV article narrative outline
1. **Hook:** A workflow failed, but the business task still finished.
2. **Problem:** Automation platforms are optimized for the happy path; recovery is fragmented.
3. **Build:** n8n connector, FastAPI ingestion, Gemma diagnosis, deterministic policy, Temporal orchestration, recovery adapters.
4. **Walkthrough:** Show real injected failure, recovery, verification, and dedup.
5. **Open innovation:** Explain how open-weight Gemma, open integration patterns, and inspectable recovery rules help builders adapt the service.
6. **Partner technology:** Describe only integrations actually implemented and their meaningful contributions.
7. **First user:** Share observed setup friction and feedback.
8. **Limitations:** One supported operation type, constrained adapters, external API uncertainty, local-vs-public Temporal availability.
9. **Links:** Repo, demo, setup, video.

## Claims to avoid
- “Works with every automation platform.”
- “Automatically fixes any error.”
- “Exactly-once execution guaranteed.”
- “Notification delivered” when provider only acknowledged acceptance.
- “Fully hosted” if Temporal worker is running only locally.
