"""Text sanitization for PETSCII output.

Two independent things happen here, not one:

1. The shared "no Unicode support" fix (renderers/_text_sanitize.py) --
   em-dash-etc substitutions + ascii-encode-with-replace fallback. Same
   logic ATASCII uses.
2. PETSCII-specific case swapping -- real, live-reported bug (2026-08-10):
   "the PETSCII version has upper and lower case letters switched."
   renderer.py sends SWITCH_TO_LOWERCASE once at construction and never
   switches back, putting the whole session in PETSCII's charset 2
   ("lowercase mode") for good. In that charset the mapping between a
   byte's numeric value and what glyph it displays is INVERTED relative to
   ASCII's own case: sending the same byte value ASCII considers 'A'-'Z'
   (65-90) displays as LOWERCASE a-z, and the byte values ASCII considers
   'a'-'z' (97-122) display as UPPERCASE A-Z. Confirmed against multiple
   independent PETSCII references (pagetable.com's "Why does PETSCII have
   upper case and lower case reversed?", HandWiki's PETSCII article) -- this
   is a well-known, deliberate quirk of the C64's character ROM, not
   something specific to this project. The fix real PETSCII-generating
   software uses is exactly this: swap the case of outgoing text BEFORE
   encoding, so the swap and the C64's own charset-2 inversion cancel out
   and the caller sees correctly-cased text. Deliberately NOT applied to
   the shared _text_sanitize module -- ATASCII has no equivalent charset
   quirk at all (confirmed during that renderer's own research: ASCII
   letters just work, no character-set switch needed), so folding this
   into the shared function would have silently broken ATASCII's case too.
"""

from .._text_sanitize import to_ascii_safe_bytes


def to_petscii_text(text: str) -> bytes:
    return to_ascii_safe_bytes(text.swapcase())


__all__ = ["to_petscii_text"]
