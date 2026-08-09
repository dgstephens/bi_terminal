"""Text sanitization for PETSCII output — PETSCII has no Unicode support at
all, and bi_terminal's specs/menus.py and core.models.field_line's default
missing-value marker both genuinely emit non-ASCII characters (confirmed by
grepping core/ and specs/ before writing this — the em dash "—" is the
main offender, used in titles, action-item labels, and every missing detail
field).

Maps known characters first (readable substitutions), then falls back to
`.encode("ascii", errors="replace")` as a safety net so any truly
unexpected character becomes "?" rather than crashing or corrupting the
byte stream — never silently dropping/mangling app text a real user would
be reading on a real C64 screen.
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


def to_petscii_text(text: str) -> bytes:
    """Sanitize and encode `text` for a PETSCII terminal. Always returns
    valid single-byte-per-character output — never raises on unexpected
    input."""
    for bad, good in _SUBSTITUTIONS.items():
        text = text.replace(bad, good)
    return text.encode("ascii", errors="replace")
