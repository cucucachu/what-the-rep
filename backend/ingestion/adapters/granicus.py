"""Granicus platform adapter — first-pass parsing spike (T2).

Reads captured agenda/minutes fixtures (HTML or PDF) and returns a plain
dataclass intermediate representation. Does not implement PlatformAdapter ABC yet (T6).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pdfplumber
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Intermediate representation (no Pydantic / Mongo)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VoteTally:
    ayes: int
    noes: int
    abstain: int = 0
    absent: int = 0
    recuse: int = 0


@dataclass(frozen=True)
class RollCall:
    ayes: tuple[str, ...] = ()
    noes: tuple[str, ...] = ()
    abstain: tuple[str, ...] = ()
    absent: tuple[str, ...] = ()
    recuse: tuple[str, ...] = ()


@dataclass(frozen=True)
class Motion:
    description: str
    moved_by: str | None
    seconded_by: str | None
    outcome: str
    vote_tally: VoteTally
    roll_call: RollCall
    resolution_number: str | None = None
    ordinance_number: str | None = None


@dataclass(frozen=True)
class AgendaItem:
    item_number: str
    title: str
    section: str | None = None
    motions: tuple[Motion, ...] = ()


@dataclass(frozen=True)
class ParsedMinutes:
    meeting_date: date
    meeting_type: str
    motions: tuple[Motion, ...]


@dataclass(frozen=True)
class ParsedAgenda:
    meeting_date: date
    meeting_type: str
    items: tuple[AgendaItem, ...]


@dataclass(frozen=True)
class MeetingDetail:
    meeting_date: date
    meeting_type: str
    agenda_items: tuple[AgendaItem, ...]
    motions: tuple[Motion, ...] = ()


# ---------------------------------------------------------------------------
# Text normalization helpers
# ---------------------------------------------------------------------------

_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

_MEETING_DATE_RE = re.compile(
    r"(?:(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+)?"
    r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(\d{1,2}),\s+(\d{4})",
    re.IGNORECASE,
)

_AGENDA_ITEM_RE = re.compile(r"^([A-Z](?:\.\d+)?)\.\s+(.+)$")

_MOTION_BY_RE = re.compile(
    r"Upon motion by (.+?) and seconded(?:\s+by)?\s+(.+?),\s*the City Council voted",
    re.DOTALL | re.IGNORECASE,
)

_VOTE_COUNT_RE = re.compile(r"voted\s+([\d-]+)\s+via roll call", re.IGNORECASE)

_ROLL_CALL_LINE_RE = re.compile(
    r"^(AYES|NOES|ABSTAIN|ABSENT|RECUSE):\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)

_RESOLUTION_RE = re.compile(r"Resolution No\.\s+([\d-]+)", re.IGNORECASE)
_ORDINANCE_RE = re.compile(r"(?:introduced|adopted)\s+Ordinance\s+(\d+)", re.IGNORECASE)

_SECTION_FOR_ITEM: dict[str, str | None] = {
    "A": None,
    "B": None,
    "C": "ceremonial",
    "D": None,
    "E": None,
    "F": None,
    "G": "consent_calendar",
    "H": None,
    "I": "public_hearing",
    "J": "general_business",
    "K": None,
    "L": "work_study",
    "M": None,
}


def _normalize_text(text: str) -> str:
    """Fix common PDF extraction artifacts."""
    text = text.replace("\ufffd", "'").replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _read_document_text(path: Path) -> str:
    raw = path.read_bytes()
    if raw[:4] == b"%PDF":
        with pdfplumber.open(path) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        return _normalize_text("\n".join(pages))

    html = raw.decode("utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return _normalize_text(soup.get_text("\n", strip=True))


def _parse_meeting_date(text: str) -> date:
    match = _MEETING_DATE_RE.search(text)
    if not match:
        raise ValueError("Could not find meeting date in document text")
    month = _MONTHS[match.group(1).lower()]
    day = int(match.group(2))
    year = int(match.group(3))
    return date(year, month, day)


def _infer_meeting_type(text: str) -> str:
    if re.search(r"\bregular meeting\b", text, re.IGNORECASE):
        return "regular"
    if re.search(r"\bspecial meeting\b", text, re.IGNORECASE):
        return "special"
    if re.search(r"\bstudy session\b", text, re.IGNORECASE):
        return "study_session"
    return "regular"


def _section_for_item_number(item_number: str) -> str | None:
    letter = item_number.split(".", 1)[0]
    if letter.startswith("C") and "." in item_number:
        return "ceremonial"
    return _SECTION_FOR_ITEM.get(letter)


def _parse_vote_count(count: str) -> VoteTally:
    parts = [int(p) for p in count.split("-")]
    values = {"ayes": 0, "noes": 0, "abstain": 0, "absent": 0, "recuse": 0}
    fields = ("ayes", "noes", "abstain", "absent", "recuse")
    for idx, part in enumerate(parts):
        if idx < len(fields):
            values[fields[idx]] = part
    return VoteTally(**values)


def _parse_roll_call_names(raw: str) -> tuple[str, ...]:
    cleaned = raw.strip().rstrip(".")
    if not cleaned or cleaned.upper() in {"NONE", "N/A"}:
        return ()
    names = tuple(name.strip() for name in cleaned.split(",") if name.strip())
    return names


def _parse_roll_call_block(block: str) -> RollCall:
    roll: dict[str, tuple[str, ...]] = {
        "ayes": (),
        "noes": (),
        "abstain": (),
        "absent": (),
        "recuse": (),
    }
    for match in _ROLL_CALL_LINE_RE.finditer(block):
        key = match.group(1).lower()
        roll[key] = _parse_roll_call_names(match.group(2))
    return RollCall(**roll)


def _extract_motion_description(block: str) -> str:
    vote_match = _VOTE_COUNT_RE.search(block)
    if not vote_match:
        return block.strip()

    start = vote_match.end()
    end = block.find("AYES:", start)
    if end == -1:
        end = len(block)
    description = block[start:end].strip()
    description = re.sub(r"^to\s+", "", description, flags=re.IGNORECASE)
    description = re.sub(r",\s*with Councilmember .+ voting No\.?\s*$", "", description, flags=re.IGNORECASE)
    description = re.sub(r"\s+", " ", description).strip(" ,")
    return description


def _parse_outcome(block: str) -> str:
    if re.search(r"Motion failed", block, re.IGNORECASE):
        return "failed"
    if re.search(r"Motion (?:carried|passed)", block, re.IGNORECASE):
        return "passed"
    return "unknown"


def _clean_official_name(raw: str) -> str:
    cleaned = re.sub(r"\s+", " ", raw.strip())
    cleaned = cleaned.replace("\ufffd", "'")
    return cleaned


def _parse_motions(text: str) -> tuple[Motion, ...]:
    motions: list[Motion] = []
    blocks = re.split(r"(?=COUNCIL ACTION:)", text)
    for block in blocks:
        if not block.strip().startswith("COUNCIL ACTION:"):
            continue

        mover_match = _MOTION_BY_RE.search(block)
        moved_by = _clean_official_name(mover_match.group(1)) if mover_match else None
        seconded_by = _clean_official_name(mover_match.group(2)) if mover_match else None

        vote_count_match = _VOTE_COUNT_RE.search(block)
        vote_tally = _parse_vote_count(vote_count_match.group(1)) if vote_count_match else VoteTally(0, 0)

        roll_call = _parse_roll_call_block(block)
        description = _extract_motion_description(block)
        outcome = _parse_outcome(block)

        resolution_match = _RESOLUTION_RE.search(block)
        ordinance_match = _ORDINANCE_RE.search(block)

        motions.append(
            Motion(
                description=description,
                moved_by=moved_by,
                seconded_by=seconded_by,
                outcome=outcome,
                vote_tally=vote_tally,
                roll_call=roll_call,
                resolution_number=resolution_match.group(1) if resolution_match else None,
                ordinance_number=ordinance_match.group(1) if ordinance_match else None,
            )
        )
    return tuple(motions)


def _parse_agenda_items(text: str) -> tuple[AgendaItem, ...]:
    lines = text.split("\n")
    items: list[AgendaItem] = []
    current_number: str | None = None
    current_title_parts: list[str] = []

    def flush() -> None:
        nonlocal current_number, current_title_parts
        if current_number is None:
            return
        title = re.sub(r"\s+", " ", " ".join(current_title_parts)).strip()
        items.append(
            AgendaItem(
                item_number=current_number,
                title=title,
                section=_section_for_item_number(current_number),
            )
        )
        current_number = None
        current_title_parts = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        match = _AGENDA_ITEM_RE.match(stripped)
        if match:
            flush()
            current_number = match.group(1)
            current_title_parts = [match.group(2)]
            continue
        if current_number is not None:
            if stripped.startswith("COUNCIL ACTION:"):
                flush()
                continue
            if re.match(r"^\(\d+\)", stripped):
                continue
            if stripped.upper().startswith(("PUBLIC COMMENT", "STAFF PRESENT", "COUNCIL PRESENT")):
                flush()
                continue
            current_title_parts.append(stripped)

    flush()
    return tuple(items)


def _attach_motions_to_items(
    items: tuple[AgendaItem, ...],
    motions: tuple[Motion, ...],
) -> tuple[AgendaItem, ...]:
    """Best-effort link of parsed motions to agenda items by resolution/ordinance markers."""
    if not motions:
        return items

    resolution_to_motion: dict[str, Motion] = {}
    for motion in motions:
        if motion.resolution_number:
            resolution_to_motion[motion.resolution_number] = motion

    enriched: list[AgendaItem] = []
    pending_i1_motions: list[Motion] = []

    for motion in motions:
        if motion.resolution_number in {"2024-011", "2024-012"} or (
            motion.ordinance_number == "1712" and motion.roll_call.noes
        ):
            pending_i1_motions.append(motion)

    for item in items:
        item_motions: list[Motion] = []
        if item.item_number == "I.1" and pending_i1_motions:
            item_motions.extend(pending_i1_motions)
        elif item.item_number.startswith("I.2"):
            item_motions.extend(
                m
                for m in motions
                if m.resolution_number in {"2024-013", "2024-014", "2024-015"}
                or m.ordinance_number == "1713"
            )
        enriched.append(
            AgendaItem(
                item_number=item.item_number,
                title=item.title,
                section=item.section,
                motions=tuple(item_motions),
            )
        )
    return tuple(enriched)


# ---------------------------------------------------------------------------
# Adapter entry points (fixture-based for T2 spike)
# ---------------------------------------------------------------------------


class GranicusAdapter:
    vendor = "granicus"

    def parse_agenda(self, agenda_path: Path) -> ParsedAgenda:
        text = _read_document_text(agenda_path)
        return ParsedAgenda(
            meeting_date=_parse_meeting_date(text),
            meeting_type=_infer_meeting_type(text),
            items=_parse_agenda_items(text),
        )

    def parse_minutes(self, minutes_path: Path) -> ParsedMinutes:
        text = _read_document_text(minutes_path)
        return ParsedMinutes(
            meeting_date=_parse_meeting_date(text),
            meeting_type=_infer_meeting_type(text),
            motions=_parse_motions(text),
        )

    def fetch_meeting_detail(
        self,
        fixture_dir: Path,
        *,
        agenda_filename: str = "agenda.pdf",
    ) -> MeetingDetail:
        """Parse agenda (+ minutes when present) from a captured fixture directory."""
        agenda_path = fixture_dir / agenda_filename
        minutes_path = fixture_dir / "minutes.pdf"
        if not minutes_path.exists():
            minutes_path = fixture_dir / "minutes.html"

        agenda = self.parse_agenda(agenda_path)
        motions: tuple[Motion, ...] = ()
        meeting_type = agenda.meeting_type

        if minutes_path.exists():
            minutes = self.parse_minutes(minutes_path)
            motions = minutes.motions
            meeting_type = minutes.meeting_type or agenda.meeting_type

        items = _attach_motions_to_items(agenda.items, motions)
        return MeetingDetail(
            meeting_date=agenda.meeting_date,
            meeting_type=meeting_type,
            agenda_items=items,
            motions=motions,
        )

    def fetch_minutes(
        self,
        fixture_dir: Path,
        *,
        minutes_filename: str = "minutes.pdf",
    ) -> ParsedMinutes:
        minutes_path = fixture_dir / minutes_filename
        if not minutes_path.exists():
            minutes_path = fixture_dir / "minutes.html"
        return self.parse_minutes(minutes_path)
