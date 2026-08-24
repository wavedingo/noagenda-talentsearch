"""Filters for the stage chrome.

These live in core rather than candidates because the polaroid is rendered by
candidates, ratings and the home page, and none of those apps owns it.
"""

import zlib

from django import template

register = template.Library()

TILT_SPAN = 2.4  # degrees either side of straight


@register.filter
def tilt(value):
    """A stable rotation for a polaroid, derived from the candidate's slug.

    Deterministic across processes on purpose, which is why this is crc32 and
    not hash(): Python salts string hashing per interpreter, so hash() would
    lean the same card a different way on each worker, and a card would appear
    to jump between page loads.
    """
    if not value:
        return "0deg"
    checksum = zlib.crc32(str(value).encode("utf-8"))
    offset = (checksum % 2001) / 1000 - 1  # -1.0 .. 1.0
    return f"{offset * TILT_SPAN:.2f}deg"


@register.filter
def star_fill(average):
    """How many of the five glyphs are filled for a given average.

    Clamped so a bad aggregate can never render six stars or a negative row.
    """
    try:
        return max(0, min(5, int(round(float(average)))))
    except (TypeError, ValueError):
        return 0
