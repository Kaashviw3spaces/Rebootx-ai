# REBOOTX — Execution Plan

**Build window:** October 13–18, 2026 (verify official submission deadline and timezone)

## Checkpoint 2 implementation status (October 13)

- [x] Preserve Checkpoint 1 HMAC ingestion, tenant read authentication, deduplication, and composite tenant constraints.
- [x] Add a transactional outbox in the incident commit; use deterministic Temporal IDs and retryable, lease-fenced dispatch.
- [x] Implement `IncidentRecoveryWorkflow` with deterministic mock diagnosis, bounded mock retry/fallback, verification, and escalation.
- [x] Persist tenant-scoped recovery state, attempts, timestamps, failure codes, verification, and idempotent audit steps.
- [x] Add tenant-authorized recovery, attempt, and timeline endpoints.
- [x] Add additive revision `0002`, retaining existing data and revision `0001`.
- [x] Validate the official SDK and native Windows development server without Docker/WSL.
- [x] Run real Temporal lifecycle/retry/duplicate-start/replay tests and actual worker-process crash/restart against a running native server.
- [x] Run SQLite regression/unit tests; run isolated live PostgreSQL tests separately and record final evidence in `backend/IMPLEMENTATION.md`.

Checkpoint 2 accepts a webhook after durable database queueing; Temporal need not be online at that moment. No real notification adapter or Gemma integration is implied by the mock recovery status. The wider end-to-end gates below remain future work.

Checkpoint 3 should add an explicit policy/approval model, a registered sandbox adapter with operation reconciliation and idempotency, and evidence-backed verification before enabling any external effects. Then integrate schema-validated Gemma proposals behind the policy gate. Revalidate unknown-outcome handling, tenant isolation, retry budgets, and worker interruption with real sandbox evidence. Assess durable server hosting and cost explicitly; never assume Temporal Cloud is free. Add operator reconciliation for workflow failures/timeouts and revoked registrations before claiming production resilience.

## Strategy
Ship a narrow, end-to-end, **real external n8n failure → authenticated event → Temporal recovery → verified provider acceptance → auditable dashboard** path before adding polish. Treat partner integrations as meaningful enhancements, not blockers to the core flow.

## Oct 13 — Contracts and foundation
- [ ] Confirm challenge rules, partner eligibility, deadline, deployment/credit constraints.
- [ ] Select primary/backup notification adapters with test-mode APIs; decide provider-acceptance verification semantics.
- [ ] Initialize monorepo, env examples, license, README, issue board.
- [ ] Define event JSON schema, AI plan schema, policy/action schema, incident state machine.
- [ ] Bootstrap Postgres, Temporal dev server, FastAPI, React.
- [ ] Build tenant/workflow/incident models and migrations.
- [ ] Create synthetic two-tenant demo data.

**Gate:** one authenticated event creates one incident and Temporal execution; duplicate event deduplicates.

## Oct 14 — External integration and deterministic recovery
- [ ] Build n8n normal workflow and n8n error workflow template; document import/setup.
- [ ] Implement webhook auth, validation, event-to-workflow mapping.
- [ ] Implement primary and backup notification adapters (real test/sandbox calls where feasible).
- [ ] Implement operation idempotency and reconciliation lookup.
- [ ] Add bounded retries/backoff and escalation state.
- [ ] Add integration tests for primary 503, fallback success, and both failing.

**Gate:** externally triggered n8n failure results in fallback action and audit trail with Gemma disabled.

## Oct 15 — Gemma and policy engine
- [ ] Connect Gemma open-weight inference; document runtime, model version, license, prompt/data handling.
- [ ] Require schema-validated plans; build rule-based fallback.
- [ ] Implement deterministic action allowlist, approval gates, attempt/time budgets.
- [ ] Add adversarial tests for prompt injection, invalid plans, credential errors, unknown outcomes.
- [ ] Log model suggestions separately from actual executed actions.

**Gate:** AI changes recommendation order but cannot expand permissions or trigger unsafe actions.

## Oct 16 — Dashboard and partner features
- [ ] Build incident list, detail timeline, recovery status, tenant switch/login, approval UI.
- [ ] Add SerpApi optional documentation research with source links and freshness labels.
- [ ] Add ElevenLabs optional incident voice briefing, with PII redaction and opt-in.
- [ ] Add aggregate metrics and evidence view.
- [ ] Deploy Render web/API; establish a reachable Temporal worker/server path or clearly document local demo requirement.

**Gate:** judges can inspect a real incident from start to finish.

## Oct 17 — Reliability and demonstration
- [ ] Execute full scenario matrix (see DEMO_PLAN.md).
- [ ] Verify tenant isolation, duplicate webhook protection, retry caps, no secret leakage.
- [ ] Run worker interruption/restart test and check for repeated side effects.
- [ ] Record 90-second product demo and deeper technical walkthrough.
- [ ] Capture architecture diagram, traces, actual latency metrics, and screenshots.
- [ ] Get at least one outside tester to import the n8n integration and report friction.

**Gate:** three consecutive clean end-to-end runs; known limitations documented.

## Oct 18 — Submit
- [ ] Freeze features; fix critical bugs only.
- [ ] Publish GitHub repo, license, setup steps, `.env.example`, synthetic fixtures, tests.
- [ ] Publish working demo URL (or label limited deployment transparently).
- [ ] Write DEV post: what built, real demo, how built, why open innovation matters, first user feedback, limitations, relevant partner categories.
- [ ] Verify every prize category's actual requirements and submission rules.
- [ ] Submit before confirmed deadline; retain screenshots/confirmation.

## Priority ladder
**P0:** n8n external event; secure ingestion; Temporal execution; fallback adapter; dedup; verification; incident history.

**P1:** Gemma diagnosis; policy engine; tenant isolation; meaningful dashboard; escalation.

**P2:** SerpApi documentation research; ElevenLabs audio; advanced visualizations; additional error scenarios.

If behind schedule, cut P2 before cutting P0. Do not fake external integration or claim a feature is live when simulated.

## Roles (solo-friendly)
- Backend/Temporal owner: event ingestion, orchestration, adapters, tests.
- AI/policy owner: Gemma inference, constrained plans, evaluation.
- Frontend/story owner: dashboard, demo script, DEV article, screenshots.

One person can cover all roles sequentially; avoid parallel integration work without stable schemas.

## Risk register
| Risk | Impact | Mitigation |
|---|---|---|
| Temporal hosting too complex for free deployment | High | Local dev server early; assess hosting on day 1; transparent local demonstration fallback |
| Gemma inference latency/compute | High | Small suitable open-weight model; async activities; deterministic fallback |
| Notification sandbox constraints | Medium | Two simple adapters with deterministic mock mode plus at least one real external test call |
| n8n error event missing needed context | High | Explicit `operation_id` and safe reference mapping; sample integration template |
| Duplicate external side effects | Critical | Idempotency keys, status reconciliation, no blind retries on unknown outcomes |
| Prompt injection via error text/docs | High | Strict schemas, tool allowlists, never execute untrusted instructions |
| Too much scope | High | P0-first gates; one business operation; two tenants; one connector |

## Definition of done
An independent reviewer can clone the repo, follow documented setup, import the n8n template, trigger a real failure, observe a Temporal recovery, inspect the audit timeline, and reproduce an escalation and a dedup case. The README distinguishes real integrations, mocks, and planned capabilities.
