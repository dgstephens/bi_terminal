"""Case-insensitive literal substring matching — ported verbatim from
bi_python/fuzzy.py.

Despite the module/function name this is NOT fuzzy subsequence matching —
that was tried first and produced false positives once list entries got long
(name + location + type + item count concatenated), e.g. querying "bin 3"
would match "Bin 25 ... Shelf 3" since b-i-n...3 still appears in order
somewhere in that combined string. Kept the name to avoid an unrelated rename
churning every import site across specs/renderers.

Used by every renderer's filterable list widgets (ListPickerSpec,
ComboFilterSelectField) for identical filter/sort semantics — this is why it
lives in core rather than being reimplemented per renderer.
"""

from typing import Optional


def fuzzy_match(query: str, text: str) -> Optional[int]:
    """Return the index of query's first case-insensitive occurrence in text,
    or None if not found. Lower index = earlier/better match, used for sorting."""
    if not query:
        return 0
    idx = text.lower().find(query.lower())
    return idx if idx != -1 else None
