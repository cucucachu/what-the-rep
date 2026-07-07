#!/usr/bin/env python3
"""Generate deterministic E2E fixture manifest from a freshly seeded MongoDB."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parent.parent / "backend"
DOCKER_APP_ROOT = Path("/app")


def _backend_root() -> Path:
    for candidate in (DOCKER_APP_ROOT, BACKEND_ROOT):
        if (candidate / "db").is_dir():
            return candidate
    return BACKEND_ROOT


sys.path.insert(0, str(_backend_root()))

from db.client import close_client, get_db, ping  # noqa: E402

# Stable fixture keys — Mongo ObjectIds are resolved at manifest generation time.
NOVATO_MEETING_EXTERNAL_ID = "1980"
NON_UNANIMOUS_ACTION_PATTERN = "2024-011"
OFFICIAL_NAME_PATTERN = "Eklund"
EXPECTED_VOTE_TALLY = {"ayes": 4, "noes": 1}
EXPECTED_OUTCOME = "passed"
DISSENTING_VOTE = "no"
GOVERNING_BODY_NAME = "Novato City Council"


async def _vote_tallies(db, action_id: Any) -> dict[str, int]:
    votes = await db.vote_records.find({"action_id": action_id}).to_list(100)
    tallies: dict[str, int] = {}
    for vote in votes:
        position = vote.get("vote") or vote.get("position") or "unknown"
        tallies[position] = tallies.get(position, 0) + 1
    return tallies


async def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: generate_e2e_manifest.py <output.json>", file=sys.stderr)
        raise SystemExit(2)

    output_path = Path(sys.argv[1])

    if not await ping():
        print("MongoDB is not reachable", file=sys.stderr)
        raise SystemExit(1)

    db = get_db()

    meeting = await db.meetings.find_one({"external_id": NOVATO_MEETING_EXTERNAL_ID})
    if meeting is None:
        print(f"Meeting external_id={NOVATO_MEETING_EXTERNAL_ID!r} not found", file=sys.stderr)
        raise SystemExit(1)

    action = await db.actions.find_one({"external_id": {"$regex": NON_UNANIMOUS_ACTION_PATTERN}})
    if action is None:
        print(
            f"Non-unanimous action matching {NON_UNANIMOUS_ACTION_PATTERN!r} not found",
            file=sys.stderr,
        )
        raise SystemExit(1)

    tallies = await _vote_tallies(db, action["_id"])
    ayes = tallies.get("aye", 0) + tallies.get("yes", 0)
    noes = tallies.get("no", 0) + tallies.get("nay", 0)
    if ayes != EXPECTED_VOTE_TALLY["ayes"] or noes != EXPECTED_VOTE_TALLY["noes"]:
        print(
            f"Unexpected tally for action {action['_id']}: {tallies} "
            f"(expected {EXPECTED_VOTE_TALLY})",
            file=sys.stderr,
        )
        raise SystemExit(1)

    person = await db.people.find_one({"full_name": {"$regex": OFFICIAL_NAME_PATTERN}})
    if person is None:
        print(f"Official matching {OFFICIAL_NAME_PATTERN!r} not found", file=sys.stderr)
        raise SystemExit(1)

    eklund_no_vote = await db.vote_records.find_one(
        {"person_id": person["_id"], "action_id": action["_id"], "vote": DISSENTING_VOTE},
    )
    if eklund_no_vote is None:
        print(
            f"Expected {DISSENTING_VOTE!r} vote from {person.get('full_name')} on dissent action",
            file=sys.stderr,
        )
        raise SystemExit(1)

    novato = await db.jurisdictions.find_one({"slug": "novato-ca"})
    novato_id = novato["_id"] if novato else None
    officeholder_names: list[str] = []
    if novato_id is not None:
        tenures = await db.office_tenures.find({"is_current": True}).to_list(500)
        office_ids = {t["office_id"] for t in tenures}
        offices = await db.offices.find(
            {"jurisdiction_id": novato_id, "_id": {"$in": list(office_ids)}},
        ).to_list(100)
        office_by_id = {o["_id"]: o for o in offices}
        person_ids = {
            t["person_id"] for t in tenures if t["office_id"] in office_by_id
        }
        people = await db.people.find({"_id": {"$in": list(person_ids)}}).to_list(100)
        officeholder_names = sorted(p.get("full_name", "") for p in people if p.get("full_name"))

    body = await db.governing_bodies.find_one({"_id": meeting["body_id"]})
    agenda_with_actions = await db.agenda_items.find_one(
        {"meeting_id": meeting["_id"], "title": "APPROVAL OF THE FINAL AGENDA"},
    )

    manifest = {
        "novatoMeetingId": str(meeting["_id"]),
        "novatoMeetingExternalId": NOVATO_MEETING_EXTERNAL_ID,
        "novatoMeetingDatePrefix": str(meeting.get("scheduled_start", ""))[:10],
        "governingBodyName": (body or {}).get("name", GOVERNING_BODY_NAME),
        "sampleAgendaItemTitle": (agenda_with_actions or {}).get("title"),
        "nonUnanimousActionId": str(action["_id"]),
        "nonUnanimousActionExternalIdPattern": NON_UNANIMOUS_ACTION_PATTERN,
        "nonUnanimousActionDescription": action.get("description"),
        "expectedVoteTally": EXPECTED_VOTE_TALLY,
        "expectedOutcome": EXPECTED_OUTCOME,
        "dissentingOfficialId": str(person["_id"]),
        "dissentingOfficialSlug": person.get("slug"),
        "dissentingOfficialName": person.get("full_name"),
        "dissentingVote": DISSENTING_VOTE,
        "novatoOfficeholderNames": officeholder_names,
        "jurisdictionCount": await db.jurisdictions.count_documents({}),
        "meetingCount": await db.meetings.count_documents({}),
        "actionCount": await db.actions.count_documents({}),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote E2E manifest to {output_path}")

    await close_client()


if __name__ == "__main__":
    asyncio.run(main())
