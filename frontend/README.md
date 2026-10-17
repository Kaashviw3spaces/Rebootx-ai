# REBOOTX Frontend Dashboard

Premium, dark-themed SaaS dashboard for **REBOOTX** — the autonomous automation failure detection, diagnosis, and recovery platform.

## Architecture

- **Framework:** React 18 + TypeScript + Vite 6
- **Routing:** React Router v6
- **Server State & Polling:** TanStack Query v5 (7s polling for dashboard metrics, 5s for active incidents)
- **Styling & Theming:** Tailwind CSS v3 with obsidian/deep-slate palette (`#09090D`, `#111116`, `#27272F`) and purple/pink highlights (`#8B5CF6`, `#E040C9`)
- **Data Visualization:** Recharts smooth Area/Line charts with custom dark tooltips
- **Iconography:** Lucide React

## Local Development (Windows)

Because PowerShell execution policy blocks running unsigned `npm.ps1` scripts on some Windows installations, use `npm.cmd` and `npx.cmd`:

```powershell
# 1. Navigate to frontend directory
cd frontend

# 2. Install dependencies
npm.cmd install

# 3. Start development server with FastAPI proxy (:5173 -> :8000)
npm.cmd run dev
```

The Vite dev server runs at:
`http://localhost:5173`

Requests to `/api/*`, `/health`, and `/mock/*` are automatically proxied to the backend at `http://127.0.0.1:8000`.

## Production Build

```powershell
npm.cmd run build
```

Build outputs are generated in `frontend/dist/` with chunk splitting for vendor libraries, charts, icons, and query caches.

## Authentication & Security

- **In-Memory Token Model:** The dashboard uses an in-memory tenant connect session (`AuthContext`).
- **Zero Storage Leakage:** Tenant read tokens are **never** stored in `localStorage`, `sessionStorage`, browser cookies, or `VITE_*` environment variables.
- **Tenant Isolation:** Every request attaches `Authorization: Bearer <tenant_read_token>`, verified via SHA-256 against `tenants.read_token_hash`.
- **Mock Mode Invariant:** Every recovery attempt, adapter action, and verification outcome is prominently labeled `MOCK-ONLY`.

