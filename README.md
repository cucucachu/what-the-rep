# What The Rep

A civic transparency platform: public government data (councilmembers, meetings, votes, motions, proposals),
starting with Marin County, CA and its cities/towns, ingested with recorded sources into a general schema that
scales from local towns up to federal government — exposed entirely through an MCP server so both a web UI and
AI agents share one interface.

See [`MASTER_PLAN.md`](./MASTER_PLAN.md) for the full design: goals, tech stack decisions, database schema,
ingestion pipeline, MCP server surface, frontend architecture, and roadmap.

## Status

Phase 0 — foundations. Repo scaffolding + CI is in place (ticket T1); no business logic yet. See the roadmap
in `MASTER_PLAN.md` §13.

## Repo layout

```
backend/    uv-managed Python: FastMCP server, ingestion pipeline, embeddings (scaffold)
frontend/   Vite + React + TypeScript app (Vitest + Playwright configured)
scripts/    one-off helpers (seed_all.py for Docker Compose / local bootstrap)
.github/    CI workflow (runs backend pytest + frontend Vitest on every push/PR to main)
docker-compose.yml   full local stack: MongoDB + seed + backend + frontend
.env.example         template for required environment variables
```

## Prerequisites

- [`uv`](https://docs.astral.sh/uv/) (Python package manager — installs Python for you; no separate `pip`/`venv`)
- [Node.js](https://nodejs.org/) 20+ and npm
- Docker + Docker Compose (for the full local stack)

## Quick start — Docker Compose (recommended)

One command brings up MongoDB, seeds pilot data, starts the MCP backend, and serves the frontend:

```bash
docker compose up --build
```

| Service  | URL |
|----------|-----|
| Frontend | http://localhost:8080 |
| Backend MCP | http://localhost:8000/mcp/ |

The `seed` service runs once on startup (idempotent — safe on re-`up`). It creates indexes, seeds Marin
jurisdictions, loads boundaries, ingests officials, and runs the Granicus ingestion pipeline for Novato and
Marin County.

To stop and remove containers:

```bash
docker compose down
```

Add `-v` to also remove the MongoDB volume.

## Backend dev setup

Python dependencies are managed **entirely with `uv`** (`pyproject.toml` + committed `uv.lock`). No
pip/poetry/pipenv.

```bash
cd backend
uv sync          # create .venv and install from uv.lock (installs Python if needed)
uv run pytest    # run the test suite
uv run ruff check .   # lint
```

Run the MCP server locally (requires MongoDB at `MONGODB_URI`):

```bash
uv run python -m mcp_server
```

Seed data manually (same steps as the Docker `seed` service):

```bash
cd backend
uv run python ../scripts/seed_all.py
```

## Frontend dev setup

```bash
cd frontend
npm install      # install dependencies
npm run dev      # start the Vite dev server
npm test         # run Vitest unit/component tests

# End-to-end (Playwright). Browsers must be installed once:
npx playwright install
npm run test:e2e
```

> Note: `npm test` (Vitest) is what CI runs. Playwright e2e is a separate,
> non-blocking script for this phase and requires `npx playwright install`.

## Environment variables

Copy [`.env.example`](./.env.example) to `.env` and fill in real values (do **not** commit `.env`):

```bash
cp .env.example .env
```

Key variables:

- `MONGODB_URI` — MongoDB connection string (`mongodb://localhost:27017` for Docker Compose; Atlas URI for cloud dev).
- `MONGODB_DB_NAME` — database name (default `what_the_rep`).
- `MCP_HOST` / `MCP_PORT` — MCP server bind address (use `0.0.0.0` inside Docker).
- `MCP_CORS_ALLOW_ORIGINS` — comma-separated browser origins allowed to call the MCP HTTP transport (required for cross-origin frontend requests).
- `VITE_MCP_URL` — MCP endpoint baked into the frontend at build time; must be reachable from the **host browser** (e.g. `http://localhost:8000/mcp/`), not a Docker internal hostname.
- `ANTHROPIC_API_KEY` — unused until Phase 4 (the `ask_agent` agentic layer, §8); server-side only.
- `RATE_LIMIT_*` / `AGENT_DAILY_BUDGET_CALLS` — rate-limit / budget tuning (§9).

## Continuous integration

[`.github/workflows/ci.yml`](./.github/workflows/ci.yml) runs on every push/PR to `main`:

- **Backend**: `astral-sh/setup-uv` (with lockfile cache) → `uv sync --frozen` → `ruff check` → `uv run pytest`.
- **Frontend**: `npm ci` → type-check → `npm test` (Vitest).
