# Backend image (scaffold). Full runtime wiring lands in ticket T19.
# Uses the official uv image; deps are installed reproducibly from uv.lock.
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

# Install dependencies first (better layer caching), from the committed lockfile.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# Copy the rest of the source.
COPY . .

# Placeholder command — the real MCP server entrypoint arrives in a later ticket.
CMD ["uv", "run", "python", "-c", "print('what-the-rep backend scaffold')"]
