"""Action vote tally MCP-UI widget: ``ui://action-vote-tally``.

Data-flow (MVP, FastMCP 3.4.3):
- ``get_action`` returns structured JSON unchanged and updates an in-process cache.
- The linked ``ui://action-vote-tally`` resource reads that cache and calls
  ``render_action_vote_tally_html``.
- Hosts discover the widget via ``list_tools()`` → ``tool.meta["ui"]["resourceUri"]``,
  then fetch HTML via ``resources/read``.
"""

from __future__ import annotations

import html
import json
from typing import Any

ACTION_VOTE_TALLY_URI = "ui://action-vote-tally"

VOTE_GROUPS: tuple[tuple[str, str], ...] = (
    ("aye", "Ayes"),
    ("no", "Noes"),
    ("abstain", "Abstain"),
    ("absent", "Absent"),
    ("recuse", "Recuse"),
)

# Updated by ``get_action``; read by the dynamic ``ui://action-vote-tally`` resource.
_latest_action_vote_tally_data: dict[str, Any] | None = None


def set_latest_action_vote_tally_data(data: dict[str, Any]) -> None:
    """Store the most recent action vote-tally payload for the UI resource."""
    global _latest_action_vote_tally_data
    _latest_action_vote_tally_data = data


def get_latest_action_vote_tally_data() -> dict[str, Any]:
    """Return cached vote-tally data, or an empty shell for first fetch."""
    if _latest_action_vote_tally_data is None:
        return {"found": False, "action_id": None}
    return _latest_action_vote_tally_data


def voter_display_name(entry: dict[str, Any]) -> str:
    """Resolve a voter label from person data or roll-call external_id."""
    person = entry.get("person")
    if person and person.get("full_name"):
        return str(person["full_name"])

    vote_record = entry.get("vote_record") or {}
    external_id = vote_record.get("external_id") or ""
    if external_id and ":" in external_id:
        raw_name = external_id.rsplit(":", 1)[-1].strip()
        if raw_name:
            return raw_name

    return "Unresolved (Former member)"


def officeholder_display_name(holder: dict[str, Any] | None) -> str:
    """Format mover/seconder from an officeholder join payload."""
    if not holder:
        return "Unknown"
    person = holder.get("person") or {}
    office = holder.get("office") or {}
    name = person.get("full_name") or "Unknown"
    title = office.get("title")
    if title:
        return f"{name} ({title})"
    return name


def render_action_vote_tally_html(data: dict[str, Any]) -> str:
    """Render a self-contained HTML page for the action vote-tally widget."""
    if not data.get("found"):
        body = (
            '<section class="empty-state">'
            "<p>Action not found or not yet loaded.</p>"
            "</section>"
        )
    else:
        body = _render_action_body(data)

    data_json = html.escape(json.dumps(data, ensure_ascii=False))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Vote Tally — What The Rep</title>
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
      margin: 0 0 0.5rem;
      font-size: 1.15rem;
      font-weight: 600;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1rem;
      margin-bottom: 1rem;
    }}
    .meta {{
      color: var(--muted);
      font-size: 0.9em;
      margin-bottom: 0.75rem;
    }}
    .outcome {{
      display: inline-block;
      font-weight: 600;
      text-transform: capitalize;
      color: var(--accent);
    }}
    .tally-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(4.5rem, 1fr));
      gap: 0.5rem;
      margin: 0.75rem 0 1rem;
    }}
    .tally-item {{
      text-align: center;
      padding: 0.5rem;
      border: 1px solid var(--border);
      border-radius: 6px;
      background: var(--empty-bg);
    }}
    .tally-item .count {{
      font-size: 1.25rem;
      font-weight: 700;
      display: block;
    }}
    .tally-item .label {{
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: var(--muted);
    }}
    .tally-item.aye .count {{ color: var(--aye); }}
    .tally-item.no .count {{ color: var(--no); }}
    .tally-item.abstain .count {{ color: var(--abstain); }}
    .tally-item.absent .count {{ color: var(--absent); }}
    .tally-item.recuse .count {{ color: var(--recuse); }}
    .motion-meta {{
      margin: 0.75rem 0;
      font-size: 0.9em;
    }}
    .motion-meta dt {{
      font-weight: 600;
      display: inline;
    }}
    .motion-meta dd {{
      display: inline;
      margin: 0 1rem 0 0.25rem;
    }}
    .vote-group {{
      margin-top: 0.75rem;
    }}
    .vote-group h3 {{
      margin: 0 0 0.35rem;
      font-size: 0.85rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .vote-group.aye h3 {{ color: var(--aye); }}
    .vote-group.no h3 {{ color: var(--no); }}
    .vote-group.abstain h3 {{ color: var(--abstain); }}
    .vote-group.absent h3 {{ color: var(--absent); }}
    .vote-group.recuse h3 {{ color: var(--recuse); }}
    ul {{
      margin: 0;
      padding-left: 1.25rem;
    }}
    li {{ margin-bottom: 0.25rem; }}
    .unresolved {{
      font-style: italic;
      color: var(--muted);
    }}
    .empty-state {{
      background: var(--empty-bg);
      border: 1px dashed var(--border);
      border-radius: 6px;
      padding: 0.75rem;
      color: var(--muted);
      font-style: italic;
    }}
    #action-vote-tally-data {{
      display: none;
    }}
  </style>
</head>
<body>
  {body}
  <script type="application/json" id="action-vote-tally-data">{data_json}</script>
</body>
</html>"""


def _render_action_body(data: dict[str, Any]) -> str:
    action = data.get("action") or {}
    description = action.get("description") or "Action"
    outcome = action.get("outcome") or "unknown"
    tally = action.get("vote_tally") or {}

    moved_by = officeholder_display_name(data.get("moved_by"))
    seconded_by = officeholder_display_name(data.get("seconded_by"))

    tally_html = _render_tally_grid(tally)
    roll_call_html = _render_roll_call_groups(data.get("vote_records") or [])

    return (
        f'<section class="card">'
        f"<h1>{html.escape(description)}</h1>"
        f'<p class="meta">Outcome: <span class="outcome">{html.escape(outcome)}</span></p>'
        f"{tally_html}"
        f'<dl class="motion-meta">'
        f"<dt>Moved by:</dt><dd>{html.escape(moved_by)}</dd>"
        f"<dt>Seconded by:</dt><dd>{html.escape(seconded_by)}</dd>"
        f"</dl>"
        f"{roll_call_html}"
        f"</section>"
    )


_TALLY_KEYS: tuple[tuple[str, str, str], ...] = (
    ("ayes", "Ayes", "aye"),
    ("noes", "Noes", "no"),
    ("abstain", "Abstain", "abstain"),
    ("absent", "Absent", "absent"),
    ("recuse", "Recuse", "recuse"),
)


def _render_tally_grid(tally: dict[str, Any]) -> str:
    items: list[str] = []
    for tally_key, label, css_key in _TALLY_KEYS:
        count = tally.get(tally_key, 0) or 0
        items.append(
            f'<div class="tally-item {html.escape(css_key)}">'
            f'<span class="count">{html.escape(str(count))}</span>'
            f'<span class="label">{html.escape(label)}</span>'
            f"</div>"
        )
    return f'<div class="tally-grid">{"".join(items)}</div>'


def _render_roll_call_groups(vote_records: list[dict[str, Any]]) -> str:
    grouped: dict[str, list[str]] = {key: [] for key, _ in VOTE_GROUPS}
    for entry in vote_records:
        vote_record = entry.get("vote_record") or {}
        vote = vote_record.get("vote")
        if vote not in grouped:
            continue
        name = voter_display_name(entry)
        is_unresolved = entry.get("person") is None
        css_class = ' class="unresolved"' if is_unresolved else ""
        grouped[vote].append(f"<li{css_class}>{html.escape(name)}</li>")

    sections: list[str] = []
    for key, label in VOTE_GROUPS:
        names = grouped[key]
        if not names:
            continue
        sections.append(
            f'<div class="vote-group {html.escape(key)}">'
            f"<h3>{html.escape(label)} ({len(names)})</h3>"
            f"<ul>{''.join(names)}</ul>"
            f"</div>"
        )

    if not sections:
        return '<p class="empty-state">No roll-call vote records on file.</p>'
    return "".join(sections)
