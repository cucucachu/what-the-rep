"""Home page MCP-UI widget: ``ui://home-summary``.

Data-flow (MVP, FastMCP 3.4.3):
- ``get_home_summary`` returns structured JSON and updates an in-process cache.
- The linked ``ui://home-summary`` resource is registered as a dynamic HTML factory
  that reads that cache and calls ``render_home_summary_html``.
- Hosts discover the widget via ``list_tools()`` → ``tool.meta["ui"]["resourceUri"]``,
  then fetch HTML via ``resources/read`` (not embedded in the tool call result).

This server-rendered approach is snapshot-testable and avoids MCP-UI client messaging,
which is not wired in FastMCP 3.4.3 for per-call data injection.
"""

from __future__ import annotations

import html
import json
from typing import Any

HOME_SUMMARY_URI = "ui://home-summary"

# Updated by ``get_home_summary``; read by the dynamic ``ui://home-summary`` resource.
_latest_home_summary_data: dict[str, Any] | None = None


def set_latest_home_summary_data(data: dict[str, Any]) -> None:
    """Store the most recent home-summary payload for the UI resource."""
    global _latest_home_summary_data
    _latest_home_summary_data = data


def get_latest_home_summary_data() -> dict[str, Any]:
    """Return cached home-summary data, or an empty shell for first fetch."""
    if _latest_home_summary_data is None:
        return {"jurisdiction_slugs": [], "jurisdictions": []}
    return _latest_home_summary_data


def render_home_summary_html(data: dict[str, Any]) -> str:
    """Render a self-contained HTML page for the home-summary widget."""
    jurisdictions = data.get("jurisdictions") or []
    sections: list[str] = []

    for entry in jurisdictions:
        sections.append(_render_jurisdiction_section(entry))

    if not sections:
        sections.append(
            '<section class="empty-state">'
            "<p>No jurisdictions selected.</p>"
            "</section>"
        )

    body = "\n".join(sections)
    data_json = html.escape(json.dumps(data, ensure_ascii=False))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Home Summary — What The Rep</title>
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
      margin: 0 0 1rem;
      font-size: 1.25rem;
      font-weight: 600;
    }}
    .jurisdiction {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1rem;
      margin-bottom: 1rem;
    }}
    .jurisdiction h2 {{
      margin: 0 0 0.75rem;
      font-size: 1.05rem;
      color: var(--accent);
    }}
    .subsection {{
      margin-top: 0.75rem;
    }}
    .subsection h3 {{
      margin: 0 0 0.5rem;
      font-size: 0.85rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: var(--muted);
    }}
    ul {{
      margin: 0;
      padding-left: 1.25rem;
    }}
    li {{ margin-bottom: 0.35rem; }}
    .meta {{
      color: var(--muted);
      font-size: 0.85em;
    }}
    .empty-state {{
      background: var(--empty-bg);
      border: 1px dashed var(--border);
      border-radius: 6px;
      padding: 0.75rem;
      color: var(--muted);
      font-style: italic;
    }}
    .not-found {{
      color: var(--muted);
    }}
    #home-summary-data {{
      display: none;
    }}
  </style>
</head>
<body>
  <h1>Government Activity Summary</h1>
  {body}
  <script type="application/json" id="home-summary-data">{data_json}</script>
</body>
</html>"""


def _render_jurisdiction_section(entry: dict[str, Any]) -> str:
    slug = entry.get("slug", "")
    if not entry.get("found"):
        return (
            f'<section class="jurisdiction" data-slug="{html.escape(slug)}">'
            f"<h2>{html.escape(slug)}</h2>"
            '<p class="not-found">Jurisdiction not found.</p>'
            "</section>"
        )

    jurisdiction = entry.get("jurisdiction") or {}
    name = jurisdiction.get("name") or slug
    meetings_html = _render_meetings(entry.get("recent_meetings") or [])
    actions_html = _render_actions(entry.get("notable_actions") or [])
    officeholders_html = _render_officeholders(entry.get("current_officeholders") or [])

    return (
        f'<section class="jurisdiction" data-slug="{html.escape(slug)}">'
        f"<h2>{html.escape(name)}</h2>"
        f'<div class="subsection meetings">'
        f"<h3>Recent Meetings</h3>{meetings_html}</div>"
        f'<div class="subsection actions">'
        f"<h3>Recent Votes &amp; Actions</h3>{actions_html}</div>"
        f'<div class="subsection officeholders">'
        f"<h3>Current Officeholders</h3>{officeholders_html}</div>"
        "</section>"
    )


def _render_meetings(meetings: list[dict[str, Any]]) -> str:
    if not meetings:
        return '<p class="empty-state">No recent meetings on record.</p>'
    items = []
    for meeting in meetings:
        date_str = _format_date(meeting.get("scheduled_start"))
        meeting_type = meeting.get("meeting_type") or "meeting"
        status = meeting.get("status") or ""
        meta = f"{html.escape(meeting_type)}"
        if status:
            meta += f" · {html.escape(status)}"
        items.append(f'<li><span class="meta">{date_str} — {meta}</span></li>')
    return f"<ul>{''.join(items)}</ul>"


def _render_actions(actions: list[dict[str, Any]]) -> str:
    if not actions:
        return '<p class="empty-state">No recent votes or actions on record.</p>'
    items = []
    for action in actions:
        description = action.get("description") or action.get("action_type") or "Action"
        outcome = action.get("outcome") or ""
        date_str = _format_date(action.get("effective_date"))
        tally = action.get("vote_tally") or {}
        tally_parts = []
        if tally.get("ayes") is not None:
            tally_parts.append(f"{tally['ayes']} aye")
        if tally.get("noes") is not None:
            tally_parts.append(f"{tally['noes']} no")
        tally_str = f" ({', '.join(tally_parts)})" if tally_parts else ""
        outcome_str = f" — {html.escape(outcome)}{html.escape(tally_str)}" if outcome else ""
        items.append(
            f"<li>"
            f'<span class="meta">{date_str}</span> '
            f"{html.escape(description)}{outcome_str}"
            f"</li>"
        )
    return f"<ul>{''.join(items)}</ul>"


def _render_officeholders(officeholders: list[dict[str, Any]]) -> str:
    if not officeholders:
        return '<p class="empty-state">No current officeholders on record.</p>'
    items = []
    for holder in officeholders:
        person = holder.get("person") or {}
        office = holder.get("office") or {}
        name = person.get("full_name") or "Unknown"
        title = office.get("title") or "Officeholder"
        items.append(f"<li>{html.escape(name)} — {html.escape(title)}</li>")
    return f"<ul>{''.join(items)}</ul>"


def _format_date(value: Any) -> str:
    if not value:
        return "Date unknown"
    text = str(value)
    return html.escape(text[:10] if len(text) >= 10 else text)
