"""Unit tests for home-summary HTML rendering (T12, DB-free)."""

from __future__ import annotations

from mcp_server.ui.home_summary import render_home_summary_html

SAMPLE_DATA = {
    "jurisdiction_slugs": ["novato-ca", "marin-county-ca"],
    "jurisdictions": [
        {
            "found": True,
            "slug": "novato-ca",
            "jurisdiction": {"name": "City of Novato", "slug": "novato-ca"},
            "recent_meetings": [
                {
                    "scheduled_start": "2024-01-23T19:00:00+00:00",
                    "meeting_type": "regular",
                    "status": "held",
                },
            ],
            "notable_actions": [
                {
                    "description": "Resolution 2024-011 Costco gas station appeal",
                    "outcome": "passed",
                    "effective_date": "2024-01-23",
                    "vote_tally": {"ayes": 4, "noes": 1},
                },
            ],
            "current_officeholders": [
                {
                    "person": {"full_name": "Pat Eklund"},
                    "office": {"title": "District 4 Councilmember"},
                },
            ],
        },
        {
            "found": True,
            "slug": "marin-county-ca",
            "jurisdiction": {"name": "Marin County", "slug": "marin-county-ca"},
            "recent_meetings": [
                {
                    "scheduled_start": "2024-02-06T13:30:00+00:00",
                    "meeting_type": "regular",
                    "status": "held",
                },
            ],
            "notable_actions": [
                {
                    "description": "Approve consent calendar",
                    "outcome": "passed",
                    "effective_date": "2024-02-06",
                    "vote_tally": {"ayes": 5, "noes": 0},
                },
            ],
            "current_officeholders": [
                {
                    "person": {"full_name": "Mary Sackett"},
                    "office": {"title": "District 1 Supervisor"},
                },
            ],
        },
    ],
}

EMPTY_JURISDICTION_DATA = {
    "jurisdiction_slugs": ["empty-town-ca"],
    "jurisdictions": [
        {
            "found": True,
            "slug": "empty-town-ca",
            "jurisdiction": {"name": "Town of Empty", "slug": "empty-town-ca"},
            "recent_meetings": [],
            "notable_actions": [],
            "current_officeholders": [],
        },
    ],
}


class TestRenderHomeSummaryHtml:
    def test_renders_three_sections_per_jurisdiction(self) -> None:
        html = render_home_summary_html(SAMPLE_DATA)

        assert "<h1>Government Activity Summary</h1>" in html
        assert "City of Novato" in html
        assert "Marin County" in html
        assert "Recent Meetings" in html
        assert "Recent Votes &amp; Actions" in html
        assert "Current Officeholders" in html
        assert "2024-01-23" in html
        assert "Resolution 2024-011 Costco gas station appeal" in html
        assert "Pat Eklund" in html
        assert "District 4 Councilmember" in html
        assert "Mary Sackett" in html
        assert "District 1 Supervisor" in html
        assert 'class="subsection meetings"' in html
        assert 'class="subsection actions"' in html
        assert 'class="subsection officeholders"' in html

    def test_self_contained_no_external_assets(self) -> None:
        html = render_home_summary_html(SAMPLE_DATA)

        assert "<style>" in html
        assert "http://" not in html
        assert "https://" not in html
        assert 'id="home-summary-data"' in html

    def test_graceful_empty_state_for_jurisdiction_with_no_activity(self) -> None:
        html = render_home_summary_html(EMPTY_JURISDICTION_DATA)

        assert "Town of Empty" in html
        assert "No recent meetings on record." in html
        assert "No recent votes or actions on record." in html
        assert "No current officeholders on record." in html
        assert 'class="empty-state"' in html

    def test_jurisdiction_not_found(self) -> None:
        html = render_home_summary_html(
            {
                "jurisdiction_slugs": ["missing-slug"],
                "jurisdictions": [
                    {
                        "found": False,
                        "slug": "missing-slug",
                        "jurisdiction": None,
                        "recent_meetings": [],
                        "notable_actions": [],
                        "current_officeholders": [],
                    },
                ],
            },
        )

        assert "missing-slug" in html
        assert "Jurisdiction not found." in html

    def test_empty_jurisdiction_list(self) -> None:
        html = render_home_summary_html({"jurisdiction_slugs": [], "jurisdictions": []})

        assert "No jurisdictions selected." in html
