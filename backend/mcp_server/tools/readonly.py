"""Read-only structured MCP tools (T9)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from bson import ObjectId
from fastmcp import FastMCP
from motor.motor_asyncio import AsyncIOMotorDatabase

from db.client import get_db
from mcp_server.tools.filters import (
    build_date_range_filter,
    build_effective_date_filter,
    id_lookup_filter,
    ref_lookup_filter,
    ref_lookup_values,
    regex_query_filter,
    resolve_body_id,
    resolve_jurisdiction_id,
)
from mcp_server.tools.location import resolve_location_at_point
from mcp_server.tools.serialize import serialize_doc, serialize_docs
from mcp_server.ui.action_vote_tally import (
    ACTION_VOTE_TALLY_URI,
    get_latest_action_vote_tally_data,
    render_action_vote_tally_html,
    set_latest_action_vote_tally_data,
)
from mcp_server.ui.helpers import register_html_ui_resource, ui_app_config
from mcp_server.ui.official_voting_history import (
    OFFICIAL_VOTING_HISTORY_URI,
    get_latest_official_voting_history_data,
    render_official_voting_history_html,
    set_latest_official_voting_history_data,
)

RECENT_ACTIVITY_DAYS = 90
DEFAULT_SEARCH_LIMIT = 50


async def _db() -> AsyncIOMotorDatabase:
    return get_db()


async def _fetch_officeholder_by_tenure_id(
    db: AsyncIOMotorDatabase,
    tenure_id: Any,
) -> dict[str, Any] | None:
    """Join person + office for one office-tenure id (mover/seconder display)."""
    if tenure_id is None:
        return None
    tenure = await db.office_tenures.find_one(ref_lookup_filter("_id", str(tenure_id)))
    if tenure is None:
        return None
    person = await db.people.find_one(ref_lookup_filter("_id", str(tenure["person_id"])))
    office = await db.offices.find_one(ref_lookup_filter("_id", str(tenure["office_id"])))
    return {
        "person": serialize_doc(person),
        "office_tenure": serialize_doc(tenure),
        "office": serialize_doc(office),
    }


def register_readonly_tools(mcp: FastMCP) -> None:
    """Register all read-only structured query tools on the given FastMCP instance."""

    register_html_ui_resource(
        mcp,
        ACTION_VOTE_TALLY_URI,
        lambda: render_action_vote_tally_html(get_latest_action_vote_tally_data()),
    )
    register_html_ui_resource(
        mcp,
        OFFICIAL_VOTING_HISTORY_URI,
        lambda: render_official_voting_history_html(
            get_latest_official_voting_history_data(),
        ),
    )

    @mcp.tool
    async def resolve_location(
        lat: float,
        lng: float,
        address: str | None = None,
    ) -> dict[str, Any]:
        """Resolve the jurisdiction stack for a latitude/longitude point.

        Returns the most specific matching jurisdiction (city or county) plus its
        ancestors (state, federal). Points outside the Marin pilot coverage area
        return ``covered: false`` with an explanatory message.
        """
        _ = address
        db = await _db()
        return await resolve_location_at_point(db, lat, lng)

    @mcp.tool
    async def get_jurisdiction(slug: str) -> dict[str, Any]:
        """Fetch a jurisdiction profile with bodies, officeholders, and recent activity."""
        db = await _db()
        jurisdiction = await db.jurisdictions.find_one({"slug": slug})
        if jurisdiction is None:
            return {"found": False, "slug": slug}

        jurisdiction_id = jurisdiction["_id"]
        bodies = await db.governing_bodies.find({"jurisdiction_id": jurisdiction_id}).to_list(
            length=100,
        )

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

        since = datetime.now(tz=UTC) - timedelta(days=RECENT_ACTIVITY_DAYS)
        meetings_count = await db.meetings.count_documents(
            {"jurisdiction_id": jurisdiction_id, "scheduled_start": {"$gte": since}},
        )
        latest_meeting = await db.meetings.find_one(
            {"jurisdiction_id": jurisdiction_id},
            sort=[("scheduled_start", -1)],
        )

        return {
            "found": True,
            "jurisdiction": serialize_doc(jurisdiction),
            "governing_bodies": serialize_docs(bodies),
            "current_officeholders": current_officeholders,
            "recent_activity": {
                "meetings_count_90d": meetings_count,
                "latest_meeting": serialize_doc(latest_meeting),
            },
        }

    @mcp.tool
    async def list_jurisdictions(
        parent_slug: str | None = None,
        level: str | None = None,
    ) -> dict[str, Any]:
        """Browse the jurisdiction hierarchy, optionally filtered by parent slug and/or level."""
        db = await _db()
        query: dict[str, Any] = {}

        if parent_slug is not None:
            parent = await db.jurisdictions.find_one({"slug": parent_slug}, {"_id": 1})
            if parent is None:
                return {"jurisdictions": [], "count": 0}
            query["parent_id"] = parent["_id"]

        if level is not None:
            query["level"] = level

        jurisdictions = await db.jurisdictions.find(query).sort("name", 1).to_list(length=200)
        serialized = serialize_docs(jurisdictions)
        return {"jurisdictions": serialized, "count": len(serialized)}

    @mcp.tool
    async def search_meetings(
        jurisdiction_slug: str | None = None,
        body: str | None = None,
        date_range: dict[str, str] | None = None,
        query: str | None = None,
    ) -> dict[str, Any]:
        """Search meetings by jurisdiction, governing body, date range, and/or text query."""
        db = await _db()
        meeting_filter: dict[str, Any] = {}

        jurisdiction_id = await resolve_jurisdiction_id(db, jurisdiction_slug)
        if jurisdiction_slug is not None and jurisdiction_id is None:
            return {"meetings": [], "count": 0}

        if jurisdiction_id is not None:
            meeting_filter["jurisdiction_id"] = jurisdiction_id

        if body is not None:
            if jurisdiction_id is None:
                return {"meetings": [], "count": 0}
            body_id = await resolve_body_id(db, jurisdiction_id=jurisdiction_id, body_name=body)
            if body_id is None:
                return {"meetings": [], "count": 0}
            meeting_filter["body_id"] = body_id

        meeting_filter.update(build_date_range_filter("scheduled_start", date_range))

        text_pattern = regex_query_filter(query)
        if text_pattern is not None:
            meeting_ids: set[ObjectId] = set()

            external_matches = await db.meetings.find(
                {**meeting_filter, "external_id": text_pattern},
                {"_id": 1},
            ).to_list(length=DEFAULT_SEARCH_LIMIT)
            meeting_ids.update(doc["_id"] for doc in external_matches)

            agenda_filter: dict[str, Any] = {}
            if jurisdiction_id is not None:
                agenda_filter["jurisdiction_id"] = jurisdiction_id
            agenda_filter["$or"] = [
                {"title": text_pattern},
                {"description": text_pattern},
            ]
            agenda_matches = await db.agenda_items.find(agenda_filter, {"meeting_id": 1}).to_list(
                length=DEFAULT_SEARCH_LIMIT,
            )
            meeting_ids.update(doc["meeting_id"] for doc in agenda_matches)

            if not meeting_ids:
                return {"meetings": [], "count": 0}
            meeting_filter["_id"] = {"$in": list(meeting_ids)}

        meetings = (
            await db.meetings.find(meeting_filter)
            .sort("scheduled_start", -1)
            .to_list(length=DEFAULT_SEARCH_LIMIT)
        )
        serialized = serialize_docs(meetings)
        return {"meetings": serialized, "count": len(serialized)}

    @mcp.tool
    async def get_meeting(meeting_id: str) -> dict[str, Any]:
        """Return one meeting with full agenda items, actions, and related documents."""
        db = await _db()
        id_filter = id_lookup_filter(meeting_id)
        if id_filter is None:
            return {"found": False, "meeting_id": meeting_id}

        meeting = await db.meetings.find_one(id_filter)
        if meeting is None:
            return {"found": False, "meeting_id": meeting_id}

        meeting_oid = meeting["_id"]
        body = await db.governing_bodies.find_one(
            ref_lookup_filter("_id", str(meeting["body_id"])),
        )
        agenda_items = (
            await db.agenda_items.find(ref_lookup_filter("meeting_id", str(meeting_oid)))
            .sort("item_number", 1)
            .to_list(
                length=500,
            )
        )
        actions = await db.actions.find(ref_lookup_filter("meeting_id", str(meeting_oid))).to_list(
            length=500,
        )
        actions_by_agenda = {}
        for action in actions:
            actions_by_agenda.setdefault(action["agenda_item_id"], []).append(action)

        document_ids: set[ObjectId] = set()
        for item in agenda_items:
            document_ids.update(item.get("document_ids", []))
        for action in actions:
            document_ids.update(action.get("document_ids", []))

        meeting_documents = await db.documents.find(
            {
                "related_type": "meeting",
                **ref_lookup_filter("related_id", str(meeting_oid)),
            },
        ).to_list(length=50)
        for doc in meeting_documents:
            document_ids.add(doc["_id"])

        documents = await db.documents.find({"_id": {"$in": list(document_ids)}}).to_list(
            length=200
        )
        documents_by_id = {doc["_id"]: doc for doc in documents}

        agenda_payload: list[dict[str, Any]] = []
        for item in agenda_items:
            item_actions = actions_by_agenda.get(item["_id"], [])
            item_doc_ids = set(item.get("document_ids", []))
            for action in item_actions:
                item_doc_ids.update(action.get("document_ids", []))
            agenda_payload.append(
                {
                    "agenda_item": serialize_doc(item),
                    "actions": serialize_docs(item_actions),
                    "documents": serialize_docs(
                        [
                            documents_by_id[doc_id]
                            for doc_id in item_doc_ids
                            if doc_id in documents_by_id
                        ]
                    ),
                }
            )

        return {
            "found": True,
            "meeting": serialize_doc(meeting),
            "governing_body": serialize_doc(body),
            "agenda_items": agenda_payload,
            "meeting_documents": serialize_docs(meeting_documents),
        }

    @mcp.tool
    async def search_actions(
        query: str | None = None,
        jurisdiction_slug: str | None = None,
        topic: str | None = None,
        date_range: dict[str, str] | None = None,
        outcome: str | None = None,
    ) -> dict[str, Any]:
        """Search votes, motions, and resolutions.

        The ``topic`` parameter is accepted for forward compatibility but is not
        yet applied (topic tagging is Phase 3).
        """
        _ = topic
        db = await _db()
        action_filter: dict[str, Any] = {}

        jurisdiction_id = await resolve_jurisdiction_id(db, jurisdiction_slug)
        if jurisdiction_slug is not None and jurisdiction_id is None:
            return {"actions": [], "count": 0}
        if jurisdiction_id is not None:
            action_filter["jurisdiction_id"] = jurisdiction_id

        if outcome is not None:
            action_filter["outcome"] = outcome

        action_filter.update(build_effective_date_filter(date_range))

        text_pattern = regex_query_filter(query)
        if text_pattern is not None:
            action_filter["$or"] = [
                {"description": text_pattern},
                {"external_id": text_pattern},
            ]

        actions = (
            await db.actions.find(action_filter)
            .sort([("effective_date", -1), ("_id", -1)])
            .to_list(length=DEFAULT_SEARCH_LIMIT)
        )
        serialized = serialize_docs(actions)
        return {"actions": serialized, "count": len(serialized)}

    @mcp.tool(app=ui_app_config(ACTION_VOTE_TALLY_URI))
    async def get_action(action_id: str) -> dict[str, Any]:
        """Return one action with roll-call vote records joined to people and tenures.

        The linked ``ui://action-vote-tally`` widget renders the roll-call breakdown
        server-side (tally summary, grouped voters, outcome, mover/seconder).
        """
        db = await _db()
        id_filter = id_lookup_filter(action_id)
        if id_filter is None:
            not_found = {"found": False, "action_id": action_id}
            set_latest_action_vote_tally_data(not_found)
            return not_found

        action = await db.actions.find_one(id_filter)
        if action is None:
            not_found = {"found": False, "action_id": action_id}
            set_latest_action_vote_tally_data(not_found)
            return not_found

        action_oid = action["_id"]
        meeting = await db.meetings.find_one(
            ref_lookup_filter("_id", str(action["meeting_id"])),
        )
        agenda_item = await db.agenda_items.find_one(
            ref_lookup_filter("_id", str(action["agenda_item_id"])),
        )
        vote_records = await db.vote_records.find(
            ref_lookup_filter("action_id", str(action_oid)),
        ).to_list(length=50)

        person_ids = {
            record["person_id"] for record in vote_records if record.get("person_id") is not None
        }
        tenure_ids = {
            record["office_tenure_id"]
            for record in vote_records
            if record.get("office_tenure_id") is not None
        }
        people = await db.people.find({"_id": ref_lookup_values(person_ids)}).to_list(length=50)
        tenures = await db.office_tenures.find({"_id": ref_lookup_values(tenure_ids)}).to_list(
            length=50
        )
        people_by_id = {person["_id"]: person for person in people}
        tenures_by_id = {tenure["_id"]: tenure for tenure in tenures}

        roll_call: list[dict[str, Any]] = []
        for record in vote_records:
            roll_call.append(
                {
                    "vote_record": serialize_doc(record),
                    "person": serialize_doc(people_by_id.get(record.get("person_id"))),
                    "office_tenure": serialize_doc(
                        tenures_by_id.get(record.get("office_tenure_id"))
                    ),
                }
            )

        document_ids = action.get("document_ids", [])
        documents = await db.documents.find({"_id": {"$in": document_ids}}).to_list(length=50)

        moved_by = await _fetch_officeholder_by_tenure_id(
            db,
            action.get("moved_by_office_tenure_id"),
        )
        seconded_by = await _fetch_officeholder_by_tenure_id(
            db,
            action.get("seconded_by_office_tenure_id"),
        )

        result = {
            "found": True,
            "action": serialize_doc(action),
            "meeting": serialize_doc(meeting),
            "agenda_item": serialize_doc(agenda_item),
            "vote_records": roll_call,
            "documents": serialize_docs(documents),
        }
        set_latest_action_vote_tally_data(
            {
                **result,
                "moved_by": moved_by,
                "seconded_by": seconded_by,
            },
        )
        return result

    @mcp.tool(app=ui_app_config(OFFICIAL_VOTING_HISTORY_URI))
    async def get_official(person_id: str) -> dict[str, Any]:
        """Return an official's bio, tenure history, and voting record.

        The linked ``ui://official-voting-history`` widget renders the bio header,
        tenure timeline, and voting record server-side.
        """
        db = await _db()
        id_filter = id_lookup_filter(person_id)
        if id_filter is None:
            not_found = {"found": False, "person_id": person_id}
            set_latest_official_voting_history_data(not_found)
            return not_found

        person = await db.people.find_one(id_filter)
        if person is None:
            not_found = {"found": False, "person_id": person_id}
            set_latest_official_voting_history_data(not_found)
            return not_found

        person_oid = person["_id"]
        tenures = (
            await db.office_tenures.find(ref_lookup_filter("person_id", str(person_oid)))
            .sort([("start_date", -1)])
            .to_list(length=100)
        )
        office_ids = {tenure["office_id"] for tenure in tenures}
        offices = await db.offices.find({"_id": {"$in": list(office_ids)}}).to_list(length=100)
        offices_by_id = {office["_id"]: office for office in offices}

        jurisdiction_ids = {office["jurisdiction_id"] for office in offices}
        body_ids = {office["body_id"] for office in offices if office.get("body_id")}
        jurisdictions = await db.jurisdictions.find(
            {"_id": {"$in": list(jurisdiction_ids)}}
        ).to_list(
            length=50,
        )
        bodies = await db.governing_bodies.find({"_id": {"$in": list(body_ids)}}).to_list(length=50)
        jurisdictions_by_id = {item["_id"]: item for item in jurisdictions}
        bodies_by_id = {item["_id"]: item for item in bodies}

        tenure_history: list[dict[str, Any]] = []
        for tenure in tenures:
            office = offices_by_id.get(tenure["office_id"])
            jurisdiction = None
            governing_body = None
            if office is not None:
                jurisdiction = jurisdictions_by_id.get(office["jurisdiction_id"])
                if office.get("body_id"):
                    governing_body = bodies_by_id.get(office["body_id"])
            tenure_history.append(
                {
                    "tenure": serialize_doc(tenure),
                    "office": serialize_doc(office),
                    "jurisdiction": serialize_doc(jurisdiction),
                    "governing_body": serialize_doc(governing_body),
                }
            )

        vote_records = (
            await db.vote_records.find(ref_lookup_filter("person_id", str(person_oid)))
            .sort([("_id", -1)])
            .to_list(length=DEFAULT_SEARCH_LIMIT)
        )
        action_ids = {record["action_id"] for record in vote_records}
        actions = await db.actions.find({"_id": ref_lookup_values(action_ids)}).to_list(length=200)
        actions_by_id = {action["_id"]: action for action in actions}
        meeting_ids = {action["meeting_id"] for action in actions}
        meetings = await db.meetings.find({"_id": ref_lookup_values(meeting_ids)}).to_list(
            length=200
        )
        meetings_by_id = {meeting["_id"]: meeting for meeting in meetings}

        voting_record: list[dict[str, Any]] = []
        for record in vote_records:
            action = actions_by_id.get(record["action_id"])
            meeting = meetings_by_id.get(action["meeting_id"]) if action else None
            voting_record.append(
                {
                    "vote_record": serialize_doc(record),
                    "action": serialize_doc(action),
                    "meeting": serialize_doc(meeting),
                }
            )

        result = {
            "found": True,
            "person": serialize_doc(person),
            "tenure_history": tenure_history,
            "voting_record": voting_record,
        }
        set_latest_official_voting_history_data(result)
        return result
