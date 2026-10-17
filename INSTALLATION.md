# REBOOTX — Self-Hosted Installation & Deployment Guide

This guide walks you through deploying the complete **REBOOTX** autonomous failure recovery stack on your own workstation or server using Docker Compose.

---

## 1. Architecture Overview

REBOOTX runs as a decoupled set of containerized services orchestrated via Docker Compose:

```
                                  +---------------------------+
                                  |   React SaaS Dashboard    |
                                  |     (Nginx: Port 3000)    |
                                  +-------------+-------------+
                                                |
                                      /api      | SPA Static
                                                v
+------------------------+        +---------------------------+        +------------------------+
|  n8n Webhook Trigger   |------->|   FastAPI Ingestion API   |------->|  PostgreSQL Database   |
|   (HMAC Signed Post)   |        |        (Port 8000)        |        |      (Port 5432)       |
+------------------------+        +-------------+-------------+        +-----------+------------+
                                                |                                  |
                                       Outbox   |                                  | Outbox
                                       Events   v                                  | Polling
+------------------------+        +---------------------------+        +-----------v------------+
|   Temporal Web UI      |        |     Outbox Dispatcher     |        |    Temporal Worker     |
|      (Port 8233)       |        | (Claims & Starts Workflow)|        |  (Executes Recovery)   |
+-----------+------------+        +-------------+-------------+        +-----------+------------+
            |                                   |                                  |
            +-----------------------------------+----------------------------------+
                                                |
                                                v
                                  +---------------------------+
                                  |  Temporal Server Engine   |
                                  |        (Port 7233)        |
                                  +---------------------------+
```

| Service | Container Name | Description | Port |
| :--- | :--- | :--- | :--- |
| **Frontend** | `rebootx-frontend` | React 18 + Vite SPA served via Nginx with API reverse proxy | `3000` |
| **Backend** | `rebootx-backend` | FastAPI HMAC ingestion, query endpoints, and dashboard API | `8000` |
| **Temporal Server** | `rebootx-temporal` | Temporal workflow orchestration engine (auto-setup) | `7233` |
| **Temporal UI** | `rebootx-temporal-ui` | Web interface for inspecting workflow execution history | `8233` |
| **Worker** | `rebootx-worker` | Executes `IncidentRecoveryWorkflow` and recovery activities | — |
| **Dispatcher** | `rebootx-dispatcher` | Polls transactional `recovery_outbox` and dispatches to Temporal | — |
| **Migration** | `rebootx-migration` | Applies Alembic migrations (`0001` through `0004`) | — |
| **PostgreSQL** | `rebootx-postgres` | PostgreSQL 16 database with persistent Docker volume | `5432` |

---

## 2. System Prerequisites

### Linux (Ubuntu, Debian, Fedora, Arch)
- **Docker Engine:** `24.0.0+` ([Install Docker Engine](https://docs.docker.com/engine/install/))
- **Docker Compose Plugin:** `v2.20.0+` (`docker compose version`)
- **Python:** `3.10+` (for running the setup preflight script)
- **Git:** Installed and available in PATH

### macOS (Apple Silicon / Intel)
- **Docker Desktop for Mac:** Version 4.25+ or **OrbStack**
- Ensure Docker daemon is running (`docker info`)
- **Python:** `3.10+` (`python3 --version` via Homebrew or Xcode tools)
- **Git:** Available via Command Line Tools (`xcode-select --install`)

### Windows 10 / 11 (64-bit)
- **Docker Desktop for Windows:** With WSL2 backend enabled
- Ensure Docker Desktop is started and the whale icon is active in system tray
- **PowerShell:** 5.1+ or PowerShell 7+
- **Python:** `3.10+` (from python.org or Microsoft Store)
- **Git for Windows**

---

## 3. Quickstart Installation (5 Minutes)

### Step 1: Clone the Repository
```bash
git clone https://github.com/sakshammalik260-cse/Rebootx-ai.git
cd Rebootx-ai
```

### Step 2: Run Automated Preflight & Configuration Setup

Run the setup script for your operating system. The script validates prerequisites, creates a production-ready `.env` file from `.env.example`, and generates cryptographically strong random secrets for PostgreSQL, HMAC ingestion, and the tenant read token:

#### On Linux / macOS:
```bash
chmod +x scripts/setup.sh
./scripts/setup.sh
```

#### On Windows (PowerShell):
```powershell
.\scripts\setup.ps1
```

#### Cross-Platform (Python):
```bash
python3 scripts/setup.py
# On Windows:
python scripts/setup.py
```

> [!NOTE]
> The setup script never outputs secret tokens to console or disk logs. On POSIX platforms, `.env` file permissions are set to `0600` (read/write by owner only).

---

### Step 3: Launch the Stack with Docker Compose

Start all services in detached mode:

```bash
docker compose up -d
```

Docker Compose will:
1. Start PostgreSQL and wait for its healthcheck (`pg_isready`).
2. Initialize Temporal and Temporal Visibility databases.
3. Start the Temporal Server orchestration engine.
4. Run Alembic database migrations to head (`0004_real_n8n_recovery.py`).
5. Launch FastAPI backend, Temporal worker, and outbox dispatcher.
6. Build and launch the React frontend Nginx container.

---

### Step 4: Verify Service Health

Check that all containers are running and healthy:

```bash
docker compose ps
```

Expected output:
```text
NAME                 IMAGE                     COMMAND                  SERVICE       CREATED         STATUS                   PORTS
rebootx-backend      rebootx-backend           "uvicorn app.main:ap…"   backend       1 minute ago    Up (healthy)             0.0.0.0:8000->8000/tcp
rebootx-dispatcher   rebootx-dispatcher        "python -m app.tempo…"   dispatcher    1 minute ago    Up                       
rebootx-frontend     rebootx-frontend          "/docker-entrypoint.…"   frontend      1 minute ago    Up (healthy)             0.0.0.0:3000->80/tcp
rebootx-migration    rebootx-migration         "alembic upgrade head"   migration     1 minute ago    Exited (0)               
rebootx-postgres     postgres:16-alpine        "docker-entrypoint.s…"   postgres      1 minute ago    Up (healthy)             0.0.0.0:5432->5432/tcp
rebootx-temporal     temporalio/auto-setup:... "autosetup"              temporal      1 minute ago    Up                       0.0.0.0:7233->7233/tcp
rebootx-temporal-ui  temporalio/ui:2.30.0      "./temporal-ui-serve…"   temporal-ui   1 minute ago    Up                       0.0.0.0:8233->8080/tcp
rebootx-worker       rebootx-worker            "python -m app.tempo…"   worker        1 minute ago    Up                       
```

---

### Step 5: Provision Your First Tenant & Workflow

To authenticate with the dashboard and ingest failure events, register your initial tenant:

```bash
docker compose run --rm backend python -m scripts.provision \
  --tenant-name "Acme Corp" \
  --workflow-external-id "demo-workflow-1" \
  --secret-env "N8N_WEBHOOK_SECRET" \
  --workflow-kind "side_effect_safe_demo_v1"
```

The command registers:
- A new **Tenant** with your `TENANT_READ_TOKEN` hash.
- An **Integration** linked to `N8N_WEBHOOK_SECRET`.
- An authorized **Workflow** record.

Output will display your registered IDs:
```text
Tenant ID: 0610d06e-460f-465e-8b19-f80b336fd8e7
Integration ID: 38979968-2d1f-4fd0-9307-c829e54ba58f
Workflow ID: 177a421c-a1d2-43bb-a579-22a7f5bf775e
```

---

### Step 6: Log Into the Operator Dashboard

1. Open your browser and navigate to:
   **`http://localhost:3000`**
2. Paste the `TENANT_READ_TOKEN` from your `.env` file into the login form.
3. You will enter the **REBOOTX SaaS Operator Dashboard**, showing live overview metrics, recovery timelines, active incidents, and integration statuses.

---

## 4. Configuration Reference

All settings reside in your root `.env` file:

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `APP_ENV` | `production` | Application mode (`production`, `development`, `test`) |
| `POSTGRES_USER` | `rebootx` | Database superuser username |
| `POSTGRES_PASSWORD` | *(Generated)* | High-entropy database password |
| `POSTGRES_DB` | `rebootx` | Primary database name |
| `DATABASE_URL` | *(Generated)* | Connection string used across all backend containers |
| `N8N_WEBHOOK_SECRET` | *(Generated)* | HMAC-SHA256 secret for verifying incoming failure webhooks |
| `TENANT_READ_TOKEN` | *(Generated)* | Bearer token for accessing tenant dashboard data |
| `TEMPORAL_ADDRESS` | `temporal:7233` | Temporal server gRPC address inside Docker network |
| `RECOVERY_MODE` | `mock-only` | Mode of recovery (`mock-only` vs `real_n8n`) |
| `N8N_AUTHORIZATIONS` | `[]` | JSON array of approved workflow fingerprints for real recovery |
| `AI_PROVIDER` | `mock` | Advisory diagnosis engine (`mock` vs `gemma`) |
| `GEMINI_API_KEY` | *(Empty)* | Google Gemini API key if `AI_PROVIDER=gemma` |
| `FRONTEND_PORT` | `3000` | Host port for the React dashboard |
| `BACKEND_PORT` | `8000` | Host port for FastAPI REST endpoints |
| `TEMPORAL_UI_PORT` | `8233` | Host port for Temporal Server Web UI |

---

## 5. Security & Safety Guarantees

1. **Default Mock-Only Recovery:**
   By default, `RECOVERY_MODE=mock-only`. Under mock mode, the Temporal worker executes simulated retries without mutating live n8n workflows or issuing external HTTP mutations.
2. **Strict Cryptographic Authorization for Real Recovery:**
   To enable real n8n execution retries, you must explicitly configure `RECOVERY_MODE=real_n8n` and provide an authorization entry in `N8N_AUTHORIZATIONS` containing the exact SHA-256 fingerprint of the saved workflow snapshot. Any fingerprint mismatch immediately fails closed and aborts execution.
3. **Zero Secret Leakage Invariant:**
   HMAC signing secrets, database credentials, and DPAPI keys exist strictly server-side. The frontend holds only an in-memory session token that is never persisted to `localStorage` or browser cookies.
4. **Tenant Isolation:**
   All read and write queries enforce hard foreign key and tenant scoping constraints at the database layer. Cross-tenant access is rejected with `HTTP 401/404`.

---

## 6. Common Operations & Troubleshooting

### Viewing Service Logs
```bash
# View logs from all services
docker compose logs -f

# View logs from a specific service
docker compose logs -f backend
docker compose logs -f worker
docker compose logs -f dispatcher
docker compose logs -f frontend
```

### Stopping the Services
```bash
# Stop containers without losing database data
docker compose stop

# Stop and remove containers, preserving the database volume
docker compose down
```

### Resetting Database Storage
> [!CAUTION]
> This command deletes all persistent database tables, tenants, and historical incidents.

```bash
docker compose down -v
```

### Port Conflicts
If port `3000`, `8000`, or `8233` is already in use on your host machine, edit your `.env` file:
```dotenv
FRONTEND_PORT=3001
BACKEND_PORT=8001
TEMPORAL_UI_PORT=8234
```
Then restart the stack:
```bash
docker compose up -d
```

