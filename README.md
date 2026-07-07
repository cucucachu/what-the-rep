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
.github/    CI workflow (runs backend pytest + frontend Vitest on every push/PR to main)
docker-compose.yml   local dev skeleton (backend + frontend; Mongo stays on Atlas)
.env.example         template for required environment variables
```

## Prerequisites

- [`uv`](https://docs.astral.sh/uv/) (Python package manager — installs Python for you; no separate `pip`/`venv`)
- [Node.js](https://nodejs.org/) 20+ and npm
- Docker (optional, for `docker compose`)

## Backend dev setup

Python dependencies are managed **entirely with `uv`** (`pyproject.toml` + committed `uv.lock`). No
pip/poetry/pipenv.

```bash
cd backend
uv sync          # create .venv and install from uv.lock (installs Python if needed)
uv run pytest    # run the test suite
uv run ruff check .   # lint
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

- `MONGODB_URI` — MongoDB Atlas connection string (used even in dev; see `MASTER_PLAN.md` §3).
- `ANTHROPIC_API_KEY` — unused until Phase 4 (the `ask_agent` agentic layer, §8); server-side only.
- `RATE_LIMIT_*` / `AGENT_DAILY_BUDGET_CALLS` — rate-limit / budget tuning (§9).

## Docker (local dev skeleton)

[`docker-compose.yml`](./docker-compose.yml) defines `backend` and `frontend` service stubs (the backend image
installs deps via `uv sync --frozen`). Full wiring lands in a later ticket (T19). MongoDB is not a service — it
stays on Atlas (cloud).

```bash
cp .env.example .env
docker compose config     # validate
docker compose up --build # bring up the stub services
```

## Continuous integration

[`.github/workflows/ci.yml`](./.github/workflows/ci.yml) runs on every push/PR to `main`:

- **Backend**: `astral-sh/setup-uv` (with lockfile cache) → `uv sync --frozen` → `ruff check` → `uv run pytest`.
- **Frontend**: `npm ci` → type-check → `npm test` (Vitest).
