"""Name normalization and token matching for entity resolution (T7)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

_TITLE_PREFIX_RE = re.compile(
    r"^(?:Mayor Pro Tem|Mayor|Councilmember|Supervisor)\s+",
    re.IGNORECASE,
)
_SUFFIX_RE = re.compile(r"\s+(?:Jr\.?|Sr\.?|II|III|IV)$", re.IGNORECASE)
_MIDDLE_INITIAL_RE = re.compile(r"^(?:[A-Z]\.?)\s+", re.IGNORECASE)
_DISTRICT_IN_NAME_RE = re.compile(r"District\s+(\d+)", re.IGNORECASE)
_LEADERSHIP_TITLES = frozenset({"mayor", "mayor pro tem"})
_MAYOR_OFFICE_TITLE = "mayor"


class MatchOutcome(StrEnum):
    MATCHED = "matched"
    UNRESOLVED = "unresolved"
    NO_MATCH = "no_match"


@dataclass(frozen=True)
class ParsedOfficialName:
    raw: str
    title: str | None
    name_part: str
    last_token: str
    match_tokens: frozenset[str]
    district: str | None


def _strip_punctuation(token: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", token.upper())


def last_name_token(full_name: str) -> str:
    """Uppercase last-name token from a stored ``people.full_name``."""
    cleaned = _SUFFIX_RE.sub("", full_name.strip())
    if not cleaned:
        return ""
    return cleaned.split()[-1].upper()


def match_tokens_for_full_name(full_name: str) -> frozenset[str]:
    """Comparable tokens for a person display name (handles O'Connor → OCONNOR)."""
    token = last_name_token(full_name)
    if not token:
        return frozenset()
    stripped = _strip_punctuation(token)
    variants = {token}
    if stripped:
        variants.add(stripped)
    return frozenset(variants)


def parse_official_name(raw: str | None) -> ParsedOfficialName | None:
    """Parse a roll-call or motion name into comparable tokens."""
    if not raw or not raw.strip():
        return None

    text = raw.strip().replace("\ufffd", "'")
    title_match = _TITLE_PREFIX_RE.match(text)
    title = title_match.group(0).strip() if title_match else None
    name_part = _TITLE_PREFIX_RE.sub("", text).strip() if title_match else text

    name_part = _SUFFIX_RE.sub("", name_part).strip()
    while _MIDDLE_INITIAL_RE.match(name_part):
        name_part = _MIDDLE_INITIAL_RE.sub("", name_part, count=1).strip()

    if not name_part:
        return None

    last_token = name_part.split()[-1].upper()
    stripped = _strip_punctuation(last_token)
    tokens = {last_token}
    if stripped:
        tokens.add(stripped)

    district_match = _DISTRICT_IN_NAME_RE.search(text)
    district = district_match.group(1) if district_match else None

    normalized_title = None
    if title is not None:
        normalized_title = title.lower().rstrip(".")

    return ParsedOfficialName(
        raw=text,
        title=normalized_title,
        name_part=name_part,
        last_token=last_token,
        match_tokens=frozenset(tokens),
        district=district,
    )


def is_leadership_title(title: str | None) -> bool:
    return title in _LEADERSHIP_TITLES if title else False


def is_mayor_office_title(title: str | None) -> bool:
    """True when the parsed title indicates the rotating Mayor seat (not Mayor Pro Tem)."""
    return title == _MAYOR_OFFICE_TITLE if title else False


def leadership_office_title(title: str | None) -> str | None:
    """Map a parsed motion/roll-call title to a stored office title."""
    if is_mayor_office_title(title):
        return "Mayor"
    return None
