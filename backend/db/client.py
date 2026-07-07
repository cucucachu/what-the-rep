"""Async MongoDB client and index setup (§5 indexing strategy)."""

import os
from typing import Final

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

DEFAULT_MONGODB_URI: Final[str] = "mongodb://localhost:27017"
DEFAULT_DB_NAME: Final[str] = "what_the_rep"

_client: AsyncIOMotorClient | None = None


def get_mongodb_uri() -> str:
    return os.environ.get("MONGODB_URI", DEFAULT_MONGODB_URI)


def get_db_name() -> str:
    return os.environ.get("MONGODB_DB_NAME", DEFAULT_DB_NAME)


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(get_mongodb_uri())
    return _client


def get_db(db_name: str | None = None) -> AsyncIOMotorDatabase:
    return get_client()[db_name or get_db_name()]


async def close_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


async def ping() -> bool:
    """Return True if MongoDB is reachable."""
    try:
        await get_client().admin.command("ping")
        return True
    except Exception:
        return False


async def create_indexes(db: AsyncIOMotorDatabase | None = None) -> None:
    """Create MVP indexes idempotently (safe to call multiple times)."""
    database = get_db() if db is None else db

    await database.jurisdictions.create_index("path")
    await database.jurisdictions.create_index("parent_id")
    await database.jurisdictions.create_index([("boundary", "2dsphere")])

    await database.meetings.create_index([("jurisdiction_id", 1), ("scheduled_start", 1)])
    await database.actions.create_index([("jurisdiction_id", 1), ("effective_date", 1)])
