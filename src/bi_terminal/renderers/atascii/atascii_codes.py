"""ATASCII control-code constants for the Atari 8-bit door renderer.

Every value confirmed against Wikipedia's ATASCII article (which cites the
canonical Atari OS control-code table) before being written here — see the
plan that produced this file. All exposed as single-byte `bytes` objects
(never `chr(n)`/`str`), same discipline as
`renderers/petscii/petscii_codes.py` and for the same reason: avoiding any
accidental text-encoding path corrupting a byte above 0x7F (empirically
confirmed during the PETSCII increment — Python's default UTF-8 encoding
double-encodes such bytes).

Two real differences from PETSCII, both confirmed against sources (not
assumed):
1. No character-set switch exists or is needed — ASCII 0x41-0x5A/0x61-0x7A
   map to the same readable letters with no setup step (atariarchives.org).
2. No color control codes exist at all. The only visual differentiation
   tool is inverse video, and unlike PETSCII's REVERSE_ON/OFF *toggle* (a
   mode that persists across subsequent characters), ATASCII inverse is
   per-byte: setting the high bit on an individual character inverts only
   that character, with no separate persistent state. See inverse() below.
"""

ESCAPE = bytes([27])
CURSOR_UP = bytes([28])
CURSOR_DOWN = bytes([29])
CURSOR_LEFT = bytes([30])
CURSOR_RIGHT = bytes([31])

CLR = bytes([125])
DELETE = bytes([126])  # Atari's actual backspace-role key
TAB = bytes([127])

RETURN = bytes([155])  # ATASCII's own canonical EOL marker, NOT ASCII 13
DELETE_LINE = bytes([156])
INSERT_LINE = bytes([157])
CLEAR_TAB_STOP = bytes([158])
SET_TAB_STOP = bytes([159])

BUZZER = bytes([253])
DELETE_CHAR = bytes([254])
INSERT_CHAR = bytes([255])


def inverse(data: bytes) -> bytes:
    """Sets the high bit on every byte in `data`, rendering each character
    as its inverse-video variant — confirmed (Wikipedia/atariarchives.org):
    "if the byte value of the character is between 128 and 255, the
    character is generally rendered as the inverse video variant." This is
    the ONLY text-highlighting mechanism ATASCII has; there is no separate
    "reverse mode" control code to toggle on/off the way PETSCII has."""
    return bytes((b | 0x80) & 0xFF for b in data)
