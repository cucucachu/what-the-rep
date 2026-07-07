"""Unit tests for action vote-tally HTML rendering (T13, DB-free)."""

from __future__ import annotations

from mcp_server.ui.action_vote_tally import (
    render_action_vote_tally_html,
    voter_display_name,
)

RESOLUTION_2024_011_DATA = {
    "found": True,
    "action": {
        "description": (
            "Adopt a resolution finding the proposed General Plan Land Use Map "
            "and Text Amendments (Resolution 2024-011)"
        ),
        "outcome": "passed",
        "vote_tally": {"ayes": 4, "noes": 1, "abstain": 0, "absent": 0, "recuse": 0},
    },
    "moved_by": {
        "person": {"full_name": "Tim O'Connor"},
        "office": {"title": "Mayor Pro Tem"},
    },
    "seconded_by": {
        "person": {"full_name": "Rachel Farac"},
        "office": {"title": "Mayor"},
    },
    "vote_records": [
        {
            "vote_record": {
                "vote": "aye",
                "external_id": "1980:I.1:2024-011:FARAC",
            },
            "person": {"full_name": "Rachel Farac"},
        },
        {
            "vote_record": {
                "vote": "aye",
                "external_id": "1980:I.1:2024-011:WERNICK",
            },
            "person": None,
        },
        {
            "vote_record": {
                "vote": "aye",
                "external_id": "1980:I.1:2024-011:O'CONNOR",
            },
            "person": {"full_name": "Tim O'Connor"},
        },
        {
            "vote_record": {
                "vote": "aye",
                "external_id": "1980:I.1:2024-011:MILBERG",
            },
            "person": None,
        },
        {
            "vote_record": {
                "vote": "no",
                "external_id": "1980:I.1:2024-011:EKLUND",
            },
            "person": {"full_name": "Pat Eklund"},
        },
    ],
}


class TestVoterDisplayName:
    def test_resolved_voter_uses_full_name(self) -> None:
        entry = {
            "person": {"full_name": "Pat Eklund"},
            "vote_record": {"external_id": "1980:I.1:2024-011:EKLUND"},
        }
        assert voter_display_name(entry) == "Pat Eklund"

    def test_unresolved_voter_uses_roll_call_external_id(self) -> None:
        entry = {
            "person": None,
            "vote_record": {"external_id": "1980:I.1:2024-011:WERNICK"},
        }
        assert voter_display_name(entry) == "WERNICK"

    def test_unresolved_without_external_id_falls_back(self) -> None:
        entry = {"person": None, "vote_record": {}}
        assert voter_display_name(entry) == "Unresolved (Former member)"


class TestRenderActionVoteTallyHtml:
    def test_renders_tally_outcome_roll_call_and_motion_meta(self) -> None:
        html = render_action_vote_tally_html(RESOLUTION_2024_011_DATA)

        assert "Resolution 2024-011" in html
        assert "passed" in html
        assert 'class="count">4</span>' in html
        assert 'class="count">1</span>' in html
        assert "Ayes (4)" in html
        assert "Noes (1)" in html
        assert "Rachel Farac" in html
        assert "O&#x27;Connor" in html
        assert "Pat Eklund" in html
        assert "WERNICK" in html
        assert "MILBERG" in html
        assert "Moved by:" in html
        assert "Seconded by:" in html
        assert "Mayor Pro Tem" in html

    def test_unresolved_voters_marked_with_css_class(self) -> None:
        html = render_action_vote_tally_html(RESOLUTION_2024_011_DATA)

        assert 'class="unresolved">WERNICK</li>' in html
        assert 'class="unresolved">MILBERG</li>' in html

    def test_self_contained_no_external_assets(self) -> None:
        html = render_action_vote_tally_html(RESOLUTION_2024_011_DATA)

        assert "<style>" in html
        assert "http://" not in html
        assert "https://" not in html
        assert 'id="action-vote-tally-data"' in html

    def test_not_found_state(self) -> None:
        html = render_action_vote_tally_html({"found": False, "action_id": "missing"})

        assert "Action not found or not yet loaded." in html
