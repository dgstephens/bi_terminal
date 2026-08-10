"""Text sanitization for the generic ANSI door renderer.

Thin re-export of the same shared logic PETSCII/ATASCII already use (see
renderers/_text_sanitize.py) — a real, live-reported bug (2026-08-10)
confirmed the ANSI renderer needed this too and simply never got it: unlike
PETSCII/ATASCII (binary I/O from day one specifically to avoid this class of
bug), AnsiIO.write() took plain Python str and wrote it straight to a
text-mode stream with zero sanitization. A real ANSI/BBS terminal expects
CP437 or plain ASCII, not UTF-8 -- any non-ASCII character in app text (the
em dash in the TextAreaField "single line" warning was the one that actually
got reported: it renders as 3 garbage CP437 glyphs on a real client) would
silently corrupt the screen. Safe to run over an ENTIRE composed string
including embedded CSI escape codes, not just plain text spans -- every byte
in an SGR/cursor-movement sequence (ESC, '[', digits, ';', the final letter)
is already plain ASCII, so sanitizing round-trips them unchanged; only
genuine non-ASCII characters are ever touched.
"""

from .._text_sanitize import to_ascii_safe_bytes


def to_ansi_text(text: str) -> str:
    """Sanitize `text` for a real ANSI/BBS terminal, returning `str` (not
    `bytes` like the PETSCII/ATASCII version) since AnsiIO's output stream
    is text-mode, not binary."""
    return to_ascii_safe_bytes(text).decode("ascii")


__all__ = ["to_ansi_text"]
