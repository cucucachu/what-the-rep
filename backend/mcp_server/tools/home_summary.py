"""Home page summary MCP tool (T12)."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP
from motor.motor_asyncio import AsyncIOMotorDatabase

from db.client import get_db
from mcp_server.tools.filters import resolve_jurisdiction_id
from mcp_server.tools.serialize import serialize_doc, serialize_docs
from mcp_server.ui.helpers import register_html_ui_resource, ui_app_config
from mcp_server.ui.home_summary import (
    HOME_SUMMARY_URI,
    get_latest_home_summary_data,
    render_home_summary_html,
    set_latest_home_summary_data,
)

HOME_SUMMARY_MEETINGS_LIMIT = 5
HOME_SUMMARY_ACTIONS_LIMIT = 10
EXCLUDED_ACTION_OUTCOMES = frozenset({"tabled", "withdrawn"})


async def _db() -> AsyncIOMotorDatabase:
    return get_db()


async def _fetch_current_officeholders(
    db: AsyncIOMotorDatabase,
    jurisdiction_id: Any,
) -> list[dict[str, Any]]:
    """Return current officeholders for one jurisdiction (same shape as get_jurisdiction)."""
    tenures = await db.office_tenures.find({"is_current": True}).to_list(length=500)
    office_ids = {tenure["office_id"] for tenure in tenures}
    offices = await db.offices.find(
        {"jurisdiction_id": jurisdiction_id, "_id": {"$in": list(office_ids)}},
    ).to_list(length=100)
    office_by_id = {office["_id"]: office for office in offices}

    person_ids = {
        tenure["person_id"] for tenure in tenures if tenure["office_id"] in office_by_id
    }
    people = await db.people.find({"_id": {"$in": list(person_ids)}}).to_list(length=100)
    people_by_id = {person["_id"]: person for person in people}

    current_officeholders: list[dict[str, Any]] = []
    for tenure in tenures:
        office = office_by_id.get(tenure["office_id"])
        if office is None:
            continue
        person = people_by_id.get(tenure["person_id"])
        current_officeholders.append(
            {
                "office": serialize_doc(office),
                "person": serialize_doc(person),
                "tenure": serialize_doc(tenure),
            }
        )
    return current_officeholders


async def _fetch_jurisdiction_summary(
    db: AsyncIOMotorDatabase,
    slug: str,
) -> dict[str, Any]:
    """Build one jurisdiction's home-summary slice."""
    jurisdiction_id = await resolve_jurisdiction_id(db, slug)
    if jurisdiction_id is None:
        return {
            "found": False,
            "slug": slug,
            "jurisdiction": None,
            "recent_meetings": [],
            "notable_actions": [],
            "current_officeholders": [],
        }

    jurisdiction = await db.jurisdictions.find_one({"_id": jurisdiction_id})

    meetings = (
        await db.meetings.find({"jurisdiction_id": jurisdiction_id})
        .sort("scheduled_start", -1)
        .to_list(length=HOME_SUMMARY_MEETINGS_LIMIT)
    )

    actions = (
        await db.actions.find(
            {
                "jurisdiction_id": jurisdiction_id,
                "outcome": {"$nin": list(EXCLUDED_ACTION_OUTCOMES)},
            },
        )
        .sort([("effective_date", -1), ("_id", -1)])
        .to_list(length=HOME_SUMMARY_ACTIONS_LIMIT)
    )

    officeholders = await _fetch_current_officeholders(db, jurisdiction_id)

    return {
        "found": True,
        "slug": slug,
        "jurisdiction": serialize_doc(jurisdiction),
        "recent_meetings": serialize_docs(meetings),
        "notable_actions": serialize_docs(actions),
        "current_officeholders": officeholders,
    }


async def build_home_summary(jurisdiction_slugs: list[str]) -> dict[str, Any]:
    """Query and assemble the home-summary payload for a jurisdiction stack."""
    db = await _db()
    jurisdictions = [
        await _fetch_jurisdiction_summary(db, slug) for slug in jurisdiction_slugs
    ]
    return {
        "jurisdiction_slugs": jurisdiction_slugs,
        "jurisdictions": jurisdictions,
    }


def register_home_summary_tools(mcp: FastMCP) -> None:
    """Register ``get_home_summary`` and its linked ``ui://home-summary`` resource."""

    register_html_ui_resource(
        mcp,
        HOME_SUMMARY_URI,
        lambda: render_home_summary_html(get_latest_home_summary_data()),
    )

    @mcp.tool(app=ui_app_config(HOME_SUMMARY_URI))
    async def get_home_summary(jurisdiction_slugs: list[str]) -> dict[str, Any]:
        """Return recent meetings, notable actions, and officeholders for a jurisdiction stack.

        Output shape::

            {
              "jurisdiction_slugs": ["novato-ca", "marin-county-ca"],
              "jurisdictions": [
                {
                  "found": true,
                  "slug": "novato-ca",
                  "jurisdiction": {...},
                  "recent_meetings": [...],      # up to 5 most recent by date
                  "notable_actions": [...],      # up to 10, excluding tabled/withdrawn
                  "current_officeholders": [...]
                },
                ...
              ]
            }

        Notable actions are the most recent actions whose outcome is not
        ``tabled`` or ``withdrawn`` (no importance ranking). The linked
        ``ui://home-summary`` widget renders this payload server-side.
        """
        data = await build_home_summary(jurisdiction_slugs)
        set_latest_home_summary_data(data)
        return data
