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

## Checkpoint 3 implementation status (October 13)

October 14 latency routing: deterministic structured HTTP 429/401/503 and known connection/schema-error paths avoid model calls in Gemma mode; ambiguous cases still call Gemma. Full schema/policy, approvals, source provenance, tenant isolation, committed-result idempotency and mock fallback are retained. Local benchmark medians are 0.0128–0.0190 ms (compute only), prompt size is 10.5% smaller, and hosted full-schema validation remains a separate open gate. No hosted latency improvement or end-to-end production success is claimed.

October 14 output-contract correction: added sanitized validation/envelope failure classification, a schema-derived seven-field prompt/example, bounded 60-second AI configuration, and a replay-versioned diagnosis-only 75/240-second activity budget. Existing action budgets, policy/fallback, tenant isolation and workflow deadline remain intact. One real production request returned after 23.383 seconds but failed the pre-parser envelope guard; precise retained text details are unavailable. The guard has now been separately classified/tested offline. The successful full-schema live-inference gate below remains open; do not retry automatically or claim completion from mocked/native tests.

- [x] Add official Google Gen AI SDK provider and verify the configured key's Gemma model catalog.
- [x] Add strict structured diagnosis validation and an independent deterministic policy gate.
- [x] Run inference inside the existing activity, retaining deterministic workflow commands and mock-only effects.
- [x] Preserve legacy deterministic fallback and provide explicit fallback-disabled escalation.
- [x] Add tenant-scoped diagnosis persistence via additive `0003`, leaving `0001`/`0002` unchanged.
- [x] Extend the authorized recovery response and audit evidence with diagnosis/policy metadata.
- [x] Test invalid output, provider failures, low confidence, injection/redaction, tenant isolation, persistence, native Temporal retry/replay, and existing worker restart.
- [x] Verify successful full-schema real Gemma diagnosis: one subsequent authorized ambiguous synthetic request returned in 21.622 seconds (`STOP`, 347 characters), parsed and validated all seven fields, and correctly required human approval through deterministic policy. No real action or live database operation occurred.
- [x] Preflight/ownership/TLS/drift verification, additive `0002 -> 0003` upgrade and live Neon PostgreSQL validation completed: 157 tests passed in isolated schemas; existing empty public data remained unchanged; no test schemas remain. No live Gemma or real recovery actions ran during this validation.

Checkpoint 3 defaults to mock mode; explicit `AI_PROVIDER=gemma` enables advisory diagnosis only. Real adapters, approval execution, operation reconciliation, evidence-backed external verification, and operator repair remain future work. Revalidate unknown completion and actual worker interruption with sandbox evidence before any external effects. Assess durable hosting/cost explicitly before claiming production resilience. The wider end-to-end schedule below describes future gates, not completed Checkpoint 3 capabilities.

## Checkpoint 4 implementation status (October 15)

- [x] Create exportable n8n primary workflow (`integrations/n8n/workflows/primary_order_notification.json`) with manual trigger and simulated failure injection (`/mock/primary-provider-failure`).
- [x] Create exportable n8n error workflow (`integrations/n8n/workflows/rebootx_error_handler.json`) using n8n Error Trigger node.
- [x] Implement robust JavaScript mapping and signing logic (`integrations/n8n/code_nodes/format_and_sign_failure.js`) with native Node `crypto` support and pure JS FIPS 180-4 HMAC-SHA256 sandbox fallback.
- [x] Generate stable event identifiers (`n8n:<execution_id>:<failed_step>`) ensuring deterministic deduplication across repeated deliveries.
- [x] Map n8n error context to strict `FailureEvent` schema, sanitizing references and preserving error categorization and HTTP status codes.
- [x] Verify exact-byte HMAC authentication and timestamp tolerance without weakening existing backend security.
- [x] Add automated test suite (`backend/tests/test_n8n_integration.py`): 13 tests covering workflow JSON validity, HMAC parity with Python, schema compliance, deduplication, timestamp validation, missing metadata resilience, tenant isolation, outbox claiming, Temporal recovery state machine, and escalation.
- [x] Document Docker-free Windows setup using native `npx.cmd n8n` and Temporal CLI in `integrations/n8n/README.md`.

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
- [x] Build incident list, detail timeline, recovery status, tenant switch/login, approval UI.
- [x] Add aggregate metrics, trends chart, and evidence view.
- [ ] Add SerpApi optional documentation research with source links and freshness labels.
- [ ] Add ElevenLabs optional incident voice briefing, with PII redaction and opt-in.
- [ ] Deploy Render web/API; establish a reachable Temporal worker/server path or clearly document local demo requirement.

**Gate:** judges can inspect a real incident from start to finish via live dashboard.

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


## Checkpoint 6 status (October 17, 2026): PARTIALLY COMPLETE

- [x] Audit existing checkpoints and preserve uncommitted CP5 work.
- [x] Establish retry/inspection support from installed n8n 2.43.6 public API specification and handler.
- [x] Implement opt-in demo-only authorization, workflow snapshot pinning and durable action reservations.
- [x] Integrate action/independent verification into existing Temporal activities; preserve outbox and workflow IDs.
- [x] Add additive migration and compatible dashboard provenance/evidence fields.
- [x] Add deterministic HTTP safety/failure tests and native Temporal lost-acknowledgement/replay coverage.
- [x] Provide a controlled local provider, importable safe workflow and Windows reproduction guide.
- [ ] Configure a dedicated n8n public API key (user confirmed none is configured).
- [ ] Obtain operator approval for any existing-database migration/provisioning before a live demonstration.
- [ ] Run actual n8n failure -> signed event -> Temporal retry -> independent n8n success verification -> dashboard evidence capture.
- [ ] Approve Checkpoint 6 only after the live gate succeeds. Do not substitute simulated evidence.

See [CHECKPOINT6_REPORT.md](CHECKPOINT6_REPORT.md) for exact results and [CHECKPOINT6_DEMO.md](CHECKPOINT6_DEMO.md) for configuration and commands.
