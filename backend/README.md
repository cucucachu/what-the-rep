# What The Rep — Backend

`uv`-managed Python backend scaffold for the What The Rep MCP server, ingestion
pipeline, and embeddings layer. See the repo root [`README.md`](../README.md)
and [`MASTER_PLAN.md`](../MASTER_PLAN.md) for the full design.

This directory is currently **scaffolding only** — package layout with
placeholder modules, no business logic yet.

## Dev setup

```bash
uv sync          # create .venv and install deps from uv.lock
uv run pytest    # run the test suite
uv run ruff check .   # lint
```

## Layout

```
mcp_server/   FastMCP app: tools, ui:// resources, prompts (+ middleware/)
agent/        deepagents setup + ask_agent tool
ingestion/    adapters/, pipeline/, registry/
db/           models/ (Pydantic schemas)
embeddings/   local embedding model wrapper
tests/        pytest suite
```
