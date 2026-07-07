"""Unit tests for official voting-history HTML rendering (T14, DB-free)."""

from __future__ import annotations

from mcp_server.ui.official_voting_history import render_official_voting_history_html

PAT_EKLUND_DATA = {
    "found": True,
    "person": {
        "id": "person-eklund",
        "full_name": "Pat Eklund",
        "bio": "Novato City Council member.",
    },
    "tenure_history": [
        {
            "tenure": {
                "start_date": "2020-12-01",
                "end_date": None,
                "is_current": True,
            },
            "office": {"title": "District 4 Councilmember"},
            "jurisdiction": {"name": "City of Novato"},
            "governing_body": {"name": "Novato City Council"},
        },
        {
            "tenure": {
                "start_date": "2016-12-01",
                "end_date": "2020-11-30",
                "is_current": False,
            },
            "office": {"title": "District 4 Councilmember"},
            "jurisdiction": {"name": "City of Novato"},
            "governing_body": {"name": "Novato City Council"},
        },
    ],
    "voting_record": [
        {
            "vote_record": {"vote": "no"},
            "action": {
                "description": (
                    "Adopt a resolution finding the proposed General Plan Land Use Map "
                    "and Text Amendments (Resolution 2024-011)"
                ),
                "outcome": "passed",
                "effective_date": "2024-01-23",
            },
            "meeting": {"scheduled_start": "2024-01-23T18:00:00"},
        },
        {
            "vote_record": {"vote": "aye"},
            "action": {
                "description": "Approve consent calendar item G.2",
                "outcome": "passed",
                "effective_date": "2024-01-23",
            },
            "meeting": {"scheduled_start": "2024-01-23T18:00:00"},
        },
    ],
}

EMPTY_VOTES_DATA = {
    "found": True,
    "person": {
        "id": "person-supervisor",
        "full_name": "Mary Sackett",
    },
    "tenure_history": [
        {
            "tenure": {
                "start_date": "2023-01-03",
                "end_date": None,
                "is_current": True,
            },
            "office": {"title": "District 3 Supervisor"},
            "jurisdiction": {"name": "Marin County"},
            "governing_body": {"name": "Board of Supervisors"},
        },
    ],
    "voting_record": [],
}


class TestRenderOfficialVotingHistoryHtml:
    def test_renders_bio_tenure_timeline_and_votes(self) -> None:
        html = render_official_voting_history_html(PAT_EKLUND_DATA)

        assert "Pat Eklund" in html
        assert "District 4 Councilmember" in html
        assert "City of Novato" in html
        assert "Tenure Timeline" in html
        assert "Voting Record" in html
        assert 'badge-current">Current</span>' in html
        assert "2020-12-01" in html
        assert "2024-011" in html
        assert 'class="vote-badge no">No</span>' in html
        assert "Outcome: passed" in html

    def test_empty_voting_record_renders_empty_state(self) -> None:
        html = render_official_voting_history_html(EMPTY_VOTES_DATA)

        assert "Mary Sackett" in html
        assert "District 3 Supervisor" in html
        assert "No recorded votes on file for this official." in html
        assert "Voting Record" in html

    def test_self_contained_no_external_assets(self) -> None:
        html = render_official_voting_history_html(PAT_EKLUND_DATA)

        assert "<style>" in html
        assert "http://" not in html
        assert "https://" not in html
        assert 'id="official-voting-history-data"' in html

    def test_not_found_state(self) -> None:
        html = render_official_voting_history_html({"found": False, "person_id": "missing"})

        assert "Official not found or not yet loaded." in html
