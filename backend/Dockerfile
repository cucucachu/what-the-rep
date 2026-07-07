# Backend image: uv-managed deps + MCP server entrypoint.
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

# Install dependencies first (better layer caching), from the committed lockfile.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-install-project

# Application source and repo-root seed script for the one-shot seed service.
COPY backend/ .
COPY scripts/ /scripts/

EXPOSE 8000

CMD ["uv", "run", "python", "-m", "mcp_server"]
