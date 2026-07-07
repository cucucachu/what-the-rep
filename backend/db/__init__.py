"""Database access layer."""

from db.client import (
    close_client,
    create_indexes,
    get_client,
    get_db,
    get_db_name,
    get_mongodb_uri,
    ping,
)

__all__ = [
    "close_client",
    "create_indexes",
    "get_client",
    "get_db",
    "get_db_name",
    "get_mongodb_uri",
    "ping",
]
