"""Entrypoint: ``uv run python -m mcp_server``."""

from mcp_server.app import serve


def main() -> None:
    serve()


if __name__ == "__main__":
    main()
