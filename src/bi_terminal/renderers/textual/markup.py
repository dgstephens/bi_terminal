"""Textual markup escaping — ported verbatim from bi_python/forms.py.

Textual's own Content/markup parser (NOT rich.markup — a separate, more
aggressive system) treats ANY "[...]" as an attempted style tag, including
single uppercase letters or arbitrary words like "[Shelf A]" — confirmed
empirically in bi_python's development; rich.markup.escape() and even
textual.markup.escape() (whose regex only covers lowercase-leading content)
both fail to prevent it. A manual backslash before the literal '[' is what
actually works.
"""


def lit(s: str) -> str:
    """Escape text for literal display inside markup=True Textual widgets.

    Use for any dynamic/user data embedded in a markup=True Static — e.g. a
    bin's name or description. Not needed for OptionList content built with
    markup=False (preferred there instead).
    """
    return s.replace("\\", "\\\\").replace("[", "\\[")
