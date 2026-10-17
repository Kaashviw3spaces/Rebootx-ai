# REBOOTX — Autonomous Automation Recovery Platform

REBOOTX detects, diagnoses, orchestrates recovery, and audits failures across connected automation engines (such as n8n).

## Architecture & Completed Checkpoints

1. **Checkpoint 1 — Secure Backend Foundation:**
   FastAPI, Neon PostgreSQL & SQLite support, Alembic migrations (`0001`–`0003`), exact-byte HMAC-SHA256 authenticated webhook ingestion, and immutable audit logs.
2. **Checkpoint 2 — Temporal Recovery Orchestration:**
   Durable Temporal workflows (`IncidentRecoveryWorkflow`), transactional outbox dispatcher with leased claiming, retry/fallback execution, and deterministic idempotency.
3. **Checkpoint 3 — Google Gemma 4 AI Diagnosis:**
   Structured failure diagnosis using `gemma-4-26b-a4b-it` via Google Gen AI SDK, conservative deterministic fast-path classification, strict 7-field Pydantic schema validation, and fail-closed safety policy enforcement.
4. **Checkpoint 4 — n8n Automation Engine Integration:**
   Native n8n Error Trigger integration, zero-dependency dual-engine HMAC-SHA256 signing (Node.js `crypto` with pure JS fallback), and live verified end-to-end failure ingestion.
5. **Checkpoint 5 — Premium Dark SaaS Dashboard:**
   Production-ready React 18, TypeScript, and Vite dashboard featuring an obsidian/deep-slate design system (`#09090D`, `#111116`), Recharts analytics, 7-second live TanStack Query polling, in-memory tenant authentication, and signature incident deep-dive view.

> [!NOTE]
> **Operational Boundary:** Recovery defaults to **mock-only**. Checkpoint 6 adds an opt-in n8n 2.43.6 public-API retry adapter with independent verification and durable duplicate prevention. **Checkpoint 6 is PARTIALLY COMPLETE: live n8n recovery was not run because no public API key is configured.** See [implementation report](docs/CHECKPOINT6_REPORT.md) and [controlled Windows demo](docs/CHECKPOINT6_DEMO.md).

## Self-Hosted Installation (Docker Compose)

For production deployment and end-to-end self-hosting across Linux, macOS, and Windows:

```bash
# 1. Clone repository
git clone https://github.com/sakshammalik260-cse/Rebootx-ai.git
cd Rebootx-ai

# 2. Run automated preflight & environment configuration
# On Linux / macOS:
./scripts/setup.sh
# On Windows (PowerShell):
.\scripts\setup.ps1

# 3. Start all services in detached mode
docker compose up -d

# 4. Provision initial tenant and demo workflow
docker compose run --rm backend python -m scripts.provision \
  --tenant-name "Primary Demo Tenant" \
  --workflow-external-id "demo-workflow-1" \
  --secret-env "N8N_WEBHOOK_SECRET" \
  --workflow-kind "side_effect_safe_demo_v1"
```

Access the services:
- **Operator Dashboard:** [http://localhost:3000](http://localhost:3000) (Log in with `TENANT_READ_TOKEN` from `.env`)
- **FastAPI REST API / Swagger:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Temporal Web UI:** [http://localhost:8233](http://localhost:8233)

See [INSTALLATION.md](INSTALLATION.md) for detailed platform-specific prerequisites, configuration variables, volume management, and operational runbooks.

## Local Development Setup (Windows)

### 1. Backend Setup
```powershell
# Navigate to backend
cd backend

# Run automated test suite (224 tests)
.\.venv\Scripts\python.exe -m pytest tests/ -v -p no:cacheprovider --basetemp .pytest_tmp

# Start FastAPI server
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

### 2. Frontend Dashboard Setup
```powershell
# In a new terminal, navigate to frontend
cd frontend

# Install dependencies
npm.cmd install

# Run frontend tests
npm.cmd test

# Build production bundle
npm.cmd run build

# Start Vite dev server (proxies /api to :8000)
npm.cmd run dev
```

Open `http://localhost:5173` in your browser. Enter your tenant read token to connect to your workspace.

## Documentation Links

- [Self-Hosted Installation Guide](INSTALLATION.md)
- [Frontend Documentation & Setup](frontend/README.md)
- [Backend Implementation & Checkpoint Audit](backend/IMPLEMENTATION.md)
- [Technical Architecture](docs/ARCHITECTURE.md)
- [Execution Plan](docs/EXECUTION_PLAN.md)
- [n8n Integration Guide](integrations/n8n/README.md)


## Checkpoint 6: real n8n recovery (partial, October 17, 2026)

The existing Temporal pipeline supports an explicitly authorized `retry_execution` on a reviewed, snapshot-pinned, side-effect-safe demo workflow. `RECOVERY_MODE=mock-only` remains the default; enabling `real_n8n` also requires credentials, an exact tenant/integration/workflow authorization and explicit idempotency/safety declarations. Advisory AI output grants no execution permission.

Migration `0004` adds incident mode, a durable external-action reservation and verification evidence. It was tested on disposable databases; no live migration or `.env` edit was performed. A separate n8n execution-status GET must confirm success before `REAL_RECOVERY_VERIFIED` and `RECOVERED`. Unknown completion escalates without resending the action. Existing mock results remain labeled simulated.

Follow [CHECKPOINT6_DEMO.md](docs/CHECKPOINT6_DEMO.md) for configuration, native Windows commands, credential handling, supported API findings and troubleshooting. See [CHECKPOINT6_REPORT.md](docs/CHECKPOINT6_REPORT.md) for exact validation evidence and remaining blockers. No live recovery success is claimed.
