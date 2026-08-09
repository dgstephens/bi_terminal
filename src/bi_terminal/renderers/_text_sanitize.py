"""Shared text sanitization for 8-bit-terminal renderers (PETSCII, ATASCII)
— neither has any Unicode support, and bi_terminal's specs/menus.py and
core.models.field_line's default missing-value marker both genuinely emit
non-ASCII characters (confirmed by grepping core/ and specs/ before this
was first written for PETSCII — the em dash "—" is the main offender, used
in titles, action-item labels, and every missing detail field).

Extracted here (originally lived only in renderers/petscii/sanitize.py) once
building the ATASCII renderer needed the exact same fix — duplicating the
substitution table across two renderers would have been exactly the kind of
copy that goes stale if only one copy is ever updated later.

Maps known characters first (readable substitutions), then falls back to
`.encode("ascii", errors="replace")` as a safety net so any truly
unexpected character becomes "?" rather than crashing or corrupting the
byte stream — never silently dropping/mangling app text a real user would
be reading on a real 8-bit screen.
"""

_SUBSTITUTIONS = {
    "—": "-",  # em dash — the actual case that motivated this module
    "–": "-",  # en dash
    "‘": "'",  # left single quote
    "’": "'",  # right single quote
    "“": '"',  # left double quote
    "”": '"',  # right double quote
    "…": "...",  # ellipsis
    "→": "->",  # rightwards arrow
}


def to_ascii_safe_bytes(text: str) -> bytes:
    """Sanitize and encode `text` for an 8-bit terminal with no Unicode
    support. Always returns valid single-byte-per-character output — never
    raises on unexpected input."""
    for bad, good in _SUBSTITUTIONS.items():
        text = text.replace(bad, good)
    return text.encode("ascii", errors="replace")
