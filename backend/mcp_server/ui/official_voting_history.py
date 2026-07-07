"""Official voting-history MCP-UI widget: ``ui://official-voting-history``.

Data-flow (MVP, FastMCP 3.4.3):
- ``get_official`` returns structured JSON unchanged and updates an in-process cache.
- The linked ``ui://official-voting-history`` resource reads that cache and calls
  ``render_official_voting_history_html``.
- Hosts discover the widget via ``list_tools()`` → ``tool.meta["ui"]["resourceUri"]``,
  then fetch HTML via ``resources/read``.
"""

from __future__ import annotations

import html
import json
from typing import Any

OFFICIAL_VOTING_HISTORY_URI = "ui://official-voting-history"

VOTE_LABELS: dict[str, str] = {
    "aye": "Aye",
    "no": "No",
    "abstain": "Abstain",
    "absent": "Absent",
    "recuse": "Recuse",
}

# Updated by ``get_official``; read by the dynamic ``ui://official-voting-history`` resource.
_latest_official_voting_history_data: dict[str, Any] | None = None


def set_latest_official_voting_history_data(data: dict[str, Any]) -> None:
    """Store the most recent official voting-history payload for the UI resource."""
    global _latest_official_voting_history_data
    _latest_official_voting_history_data = data


def get_latest_official_voting_history_data() -> dict[str, Any]:
    """Return cached voting-history data, or an empty shell for first fetch."""
    if _latest_official_voting_history_data is None:
        return {"found": False, "person_id": None}
    return _latest_official_voting_history_data


def render_official_voting_history_html(data: dict[str, Any]) -> str:
    """Render a self-contained HTML page for the official voting-history widget."""
    if not data.get("found"):
        body = (
            '<section class="empty-state">'
            "<p>Official not found or not yet loaded.</p>"
            "</section>"
        )
    else:
        body = _render_official_body(data)

    data_json = html.escape(json.dumps(data, ensure_ascii=False))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Official Voting History — What The Rep</title>
  <style>
    :root {{
      color-scheme: light dark;
      --bg: #f8f9fb;
      --card: #ffffff;
      --text: #1a1d21;
      --muted: #5c6570;
      --border: #d8dee6;
      --accent: #1f5c99;
      --empty-bg: #eef1f5;
      --current: #1a7f37;
      --aye: #1a7f37;
      --no: #cf222e;
      --abstain: #9a6700;
      --absent: #656d76;
      --recuse: #8250df;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #12151a;
        --card: #1c2128;
        --text: #e8edf2;
        --muted: #9aa5b1;
        --border: #30363d;
        --accent: #58a6ff;
        --empty-bg: #21262d;
        --current: #3fb950;
        --aye: #3fb950;
        --no: #f85149;
        --abstain: #d29922;
        --absent: #8b949e;
        --recuse: #a371f7;
      }}
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      padding: 1rem;
      font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.45;
      font-size: 14px;
    }}
    h1 {{
      margin: 0 0 0.25rem;
      font-size: 1.25rem;
      font-weight: 600;
    }}
    h2 {{
      margin: 0 0 0.75rem;
      font-size: 0.85rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: var(--muted);
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1rem;
      margin-bottom: 1rem;
    }}
    .bio .title {{
      color: var(--muted);
      font-size: 0.95em;
      margin: 0;
    }}
    .bio .bio-text {{
      margin: 0.75rem 0 0;
      color: var(--muted);
      font-size: 0.9em;
    }}
    .timeline {{
      list-style: none;
      margin: 0;
      padding: 0;
      border-left: 2px solid var(--border);
    }}
    .timeline-item {{
      position: relative;
      padding: 0 0 1rem 1rem;
      margin-left: 0.35rem;
    }}
    .timeline-item:last-child {{
      padding-bottom: 0;
    }}
    .timeline-item::before {{
      content: "";
      position: absolute;
      left: -0.55rem;
      top: 0.35rem;
      width: 0.55rem;
      height: 0.55rem;
      border-radius: 50%;
      background: var(--border);
      border: 2px solid var(--card);
    }}
    .timeline-item.current::before {{
      background: var(--current);
    }}
    .timeline-item .office-title {{
      font-weight: 600;
      margin: 0 0 0.15rem;
    }}
    .timeline-item .meta {{
      color: var(--muted);
      font-size: 0.85em;
      margin: 0;
    }}
    .badge-current {{
      display: inline-block;
      font-size: 0.7rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: var(--current);
      border: 1px solid var(--current);
      border-radius: 4px;
      padding: 0.1rem 0.35rem;
      margin-left: 0.35rem;
      vertical-align: middle;
    }}
    .votes {{
      list-style: none;
      margin: 0;
      padding: 0;
    }}
    .vote-item {{
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0.65rem 0.75rem;
      margin-bottom: 0.5rem;
      background: var(--empty-bg);
    }}
    .vote-item:last-child {{
      margin-bottom: 0;
    }}
    .vote-item .description {{
      font-weight: 500;
      margin: 0 0 0.35rem;
    }}
    .vote-item .meta {{
      color: var(--muted);
      font-size: 0.85em;
      margin: 0;
    }}
    .vote-badge {{
      display: inline-block;
      font-weight: 600;
      font-size: 0.8rem;
      text-transform: uppercase;
      letter-spacing: 0.03em;
      padding: 0.1rem 0.4rem;
      border-radius: 4px;
      margin-right: 0.35rem;
    }}
    .vote-badge.aye {{
      color: var(--aye);
      background: color-mix(in srgb, var(--aye) 12%, transparent);
    }}
    .vote-badge.no {{
      color: var(--no);
      background: color-mix(in srgb, var(--no) 12%, transparent);
    }}
    .vote-badge.abstain {{
      color: var(--abstain);
      background: color-mix(in srgb, var(--abstain) 12%, transparent);
    }}
    .vote-badge.absent {{
      color: var(--absent);
      background: color-mix(in srgb, var(--absent) 12%, transparent);
    }}
    .vote-badge.recuse {{
      color: var(--recuse);
      background: color-mix(in srgb, var(--recuse) 12%, transparent);
    }}
    .empty-state {{
      background: var(--empty-bg);
      border: 1px dashed var(--border);
      border-radius: 6px;
      padding: 0.75rem;
      color: var(--muted);
      font-style: italic;
    }}
    #official-voting-history-data {{
      display: none;
    }}
  </style>
</head>
<body>
  {body}
  <script type="application/json" id="official-voting-history-data">{data_json}</script>
</body>
</html>"""


def _render_official_body(data: dict[str, Any]) -> str:
    person = data.get("person") or {}
    tenure_history = data.get("tenure_history") or []
    voting_record = data.get("voting_record") or []

    bio_html = _render_bio_header(person, tenure_history)
    timeline_html = _render_tenure_timeline(tenure_history)
    votes_html = _render_voting_record(voting_record)

    return (
        f"{bio_html}"
        f'<section class="card tenure">'
        f"<h2>Tenure Timeline</h2>{timeline_html}</section>"
        f'<section class="card votes-section">'
        f"<h2>Voting Record</h2>{votes_html}</section>"
    )


def _render_bio_header(person: dict[str, Any], tenure_history: list[dict[str, Any]]) -> str:
    name = person.get("full_name") or "Unknown Official"
    current = _current_tenure_entry(tenure_history)
    title_line = _format_current_title(current)
    bio = person.get("bio")
    bio_html = ""
    if bio:
        bio_html = f'<p class="bio-text">{html.escape(str(bio))}</p>'

    return (
        f'<section class="card bio">'
        f"<h1>{html.escape(name)}</h1>"
        f'<p class="title">{html.escape(title_line)}</p>'
        f"{bio_html}"
        f"</section>"
    )


def _current_tenure_entry(tenure_history: list[dict[str, Any]]) -> dict[str, Any] | None:
    for entry in tenure_history:
        tenure = entry.get("tenure") or {}
        if tenure.get("is_current"):
            return entry
    return tenure_history[0] if tenure_history else None


def _format_current_title(entry: dict[str, Any] | None) -> str:
    if entry is None:
        return "Office unknown"
    office = entry.get("office") or {}
    jurisdiction = entry.get("jurisdiction") or {}
    title = office.get("title") or "Officeholder"
    jurisdiction_name = jurisdiction.get("name")
    if jurisdiction_name:
        return f"{title}, {jurisdiction_name}"
    return title


def _render_tenure_timeline(tenure_history: list[dict[str, Any]]) -> str:
    if not tenure_history:
        return '<p class="empty-state">No tenure history on record.</p>'

    items: list[str] = []
    for entry in tenure_history:
        tenure = entry.get("tenure") or {}
        office = entry.get("office") or {}
        jurisdiction = entry.get("jurisdiction") or {}
        governing_body = entry.get("governing_body") or {}

        title = office.get("title") or "Office"
        is_current = bool(tenure.get("is_current"))
        current_badge = '<span class="badge-current">Current</span>' if is_current else ""
        css_class = "timeline-item current" if is_current else "timeline-item"

        start = _format_date(tenure.get("start_date"))
        end = _format_date(tenure.get("end_date")) if tenure.get("end_date") else "Present"
        date_range = f"{start} — {end}"

        jurisdiction_name = jurisdiction.get("name") or ""
        body_name = governing_body.get("name") or ""
        context_parts = [part for part in (jurisdiction_name, body_name) if part]
        context = " · ".join(context_parts)

        items.append(
            f'<li class="{css_class}">'
            f'<p class="office-title">{html.escape(title)}{current_badge}</p>'
            f'<p class="meta">{html.escape(date_range)}'
            f"{f' · {html.escape(context)}' if context else ''}</p>"
            f"</li>"
        )

    return f'<ul class="timeline">{"".join(items)}</ul>'


def _render_voting_record(voting_record: list[dict[str, Any]]) -> str:
    if not voting_record:
        return (
            '<p class="empty-state">'
            "No recorded votes on file for this official."
            "</p>"
        )

    items: list[str] = []
    for entry in voting_record:
        vote_record = entry.get("vote_record") or {}
        action = entry.get("action") or {}
        meeting = entry.get("meeting") or {}

        vote = vote_record.get("vote") or "unknown"
        vote_label = VOTE_LABELS.get(vote, str(vote).title())
        description = action.get("description") or action.get("action_type") or "Action"
        outcome = action.get("outcome") or ""
        meeting_date = _format_date(meeting.get("scheduled_start"))
        effective_date = _format_date(action.get("effective_date"))
        date_str = meeting_date if meeting_date != "Date unknown" else effective_date

        outcome_str = f" · Outcome: {html.escape(outcome)}" if outcome else ""

        items.append(
            f'<li class="vote-item">'
            f'<p class="description">'
            f'<span class="vote-badge {html.escape(vote)}">{html.escape(vote_label)}</span>'
            f"{html.escape(description)}"
            f"</p>"
            f'<p class="meta">{html.escape(date_str)}{outcome_str}</p>'
            f"</li>"
        )

    return f'<ul class="votes">{"".join(items)}</ul>'


def _format_date(value: Any) -> str:
    if not value:
        return "Date unknown"
    text = str(value)
    return html.escape(text[:10] if len(text) >= 10 else text)
