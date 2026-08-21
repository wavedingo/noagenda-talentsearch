"""Parsing for the No Agenda RSS feed (spec 3.4).

Pure functions only -- no database, no network. `parse_feed()` turns feed XML
into a list of dicts ready for upsert, plus a list of per-item failures.
"""

import re
from email.utils import parsedate_to_datetime

from defusedxml.ElementTree import fromstring

# The feed's `podcast:` namespace resolves to the namespace doc on GitHub, not
# the canonical https://podcastindex.org/namespace/1.0 URI -- verified against
# the live feed on 2026-08-20. Nothing here matches on a namespace URI or a
# prefix; elements are found by local name so a publisher-side namespace change
# can't silently empty the sync.
_LOCAL_NAME = re.compile(r"^\{[^}]*\}")

EPISODE_NUMBER_RE = re.compile(r"^\s*(\d+)")
NUMBER_PREFIX_RE = re.compile(r"^\s*\d+\s*[-–—]\s*")

# Straight and curly pairs. Feed titles are wrapped inconsistently.
QUOTE_PAIRS = (('"', '"'), ("'", "'"), ("“", "”"), ("‘", "’"))

# The one `podcast:person` role worth reading. `role="host"` is a boilerplate
# template value in this feed -- John C Dvorak is listed as host on 229 of 230
# items, including 1889 (the producer tribute to him) and every episode
# published since. Ingesting it would print his name as host of episodes he was
# not on. Only `guest host` is curated by hand.
GUEST_HOST_ROLE = "guest host"


class ItemParseError(Exception):
    """One `<item>` could not be parsed. The rest of the feed still syncs."""


def local_name(tag):
    return _LOCAL_NAME.sub("", tag)


def _find(element, name):
    for child in element:
        if local_name(child.tag) == name:
            return child
    return None


def _find_all(element, name):
    return [child for child in element if local_name(child.tag) == name]


def _text(element, name):
    child = _find(element, name)
    return (child.text or "") if child is not None else ""


def normalize_guid(raw_guid):
    """Reduce a permalink GUID to a stable key.

    The GUID is a URL, so a scheme change, a trailing slash, or a case
    difference would otherwise read as a brand-new episode and duplicate the
    whole back catalogue (spec 3.4).
    """
    guid = (raw_guid or "").strip().lower()
    guid = re.sub(r"^[a-z][a-z0-9+.\-]*://", "", guid)
    return guid.rstrip("/")


def parse_episode_number(title):
    """Leading digits of the title. Derived/display only -- never a key."""
    match = EPISODE_NUMBER_RE.match(title or "")
    if not match:
        raise ItemParseError(f"no leading episode number in title {title!r}")
    return int(match.group(1))


def clean_title(title):
    """Strip the `NNNN - ` prefix and any wrapping quotes.

    Feed titles carry stray whitespace inside the CDATA (`1887 - "The Stick
    Works" `) and vary in quote style, so both ends are trimmed twice: once
    around the quotes, once inside them.
    """
    cleaned = NUMBER_PREFIX_RE.sub("", title or "").strip()
    for opening, closing in QUOTE_PAIRS:
        if len(cleaned) >= 2 and cleaned.startswith(opening) and cleaned.endswith(closing):
            cleaned = cleaned[1:-1]
            break
    return cleaned.strip()


def parse_duration(raw):
    """`<itunes:duration>` is integer seconds in this feed, but HH:MM:SS and
    MM:SS are both legal in the wild -- accept them rather than lose the field
    if the publisher's tooling changes."""
    raw = (raw or "").strip()
    if not raw:
        return None
    if raw.isdigit():
        return int(raw)
    if ":" in raw:
        parts = raw.split(":")
        if len(parts) <= 3 and all(p.strip().isdigit() for p in parts):
            seconds = 0
            for part in parts:
                seconds = seconds * 60 + int(part)
            return seconds
    raise ItemParseError(f"unreadable duration {raw!r}")


def parse_published_at(raw):
    try:
        return parsedate_to_datetime(raw.strip())
    except (TypeError, ValueError, IndexError) as exc:
        raise ItemParseError(f"unreadable pubDate {raw!r}") from exc


def parse_guest_hosts(item):
    """Names from `<podcast:person role="guest host">`, in feed order."""
    names = []
    for person in _find_all(item, "person"):
        role = (person.attrib.get("role") or "").strip().lower()
        name = (person.text or "").strip()
        if role == GUEST_HOST_ROLE and name and name not in names:
            names.append(name)
    return names


def parse_item(item):
    """One `<item>` -> a dict of Episode fields. Raises ItemParseError."""
    raw_guid = _text(item, "guid").strip()
    if not raw_guid:
        raise ItemParseError("item has no guid")
    guid = normalize_guid(raw_guid)
    if not guid:
        raise ItemParseError(f"guid {raw_guid!r} normalized to nothing")

    title_raw = _text(item, "title")
    link_url = _text(item, "link").strip()
    if not link_url:
        raise ItemParseError(f"item {raw_guid!r} has no link")

    artwork = _find(item, "image")
    enclosure = _find(item, "enclosure")
    duration = _find(item, "duration")

    # `<description>` is deliberately not read: hundreds of lines of donor
    # names per episode, no use on this site, and a privacy own-goal to render.
    return {
        "guid": guid,
        "raw_guid": raw_guid,
        "episode_number": parse_episode_number(title_raw),
        "title_raw": title_raw,
        "title_display": clean_title(title_raw),
        "published_at": parse_published_at(_text(item, "pubDate")),
        "link_url": link_url,
        "artwork_url": (artwork.attrib.get("href", "") if artwork is not None else "").strip(),
        "enclosure_url": (enclosure.attrib.get("url", "") if enclosure is not None else "").strip(),
        "duration_sec": parse_duration(duration.text if duration is not None else ""),
        "feed_guest_hosts": parse_guest_hosts(item),
    }


def parse_feed(xml_bytes):
    """Feed XML -> (episodes, failures).

    Only `<item>` children of `<channel>` are considered. `<podcast:liveItem>`
    is a sibling of those items, not one of them, so the live-stream entry is
    skipped structurally rather than filtered out afterwards (spec 3.4).

    A failing item is collected into `failures` and never aborts the feed.
    """
    root = fromstring(xml_bytes)
    channel = _find(root, "channel")
    if channel is None:
        raise ValueError("feed has no <channel> element")

    episodes = []
    failures = []
    for item in _find_all(channel, "item"):
        try:
            episodes.append(parse_item(item))
        except ItemParseError as exc:
            failures.append((_text(item, "title").strip() or "<untitled>", str(exc)))
    return episodes, failures
