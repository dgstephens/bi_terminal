"""PETSCII control-code constants for the Commodore 64 door renderer.

Every value confirmed against sta.c64.org's PETSCII code table (a widely
cited authoritative reference) before being written here — see the plan
that produced this file. All exposed as single-byte `bytes` objects (never
`chr(n)`/`str`), so callers can never accidentally route a control code
through a text-encoding path — a real bug this project's own research
caught: Python's default UTF-8 text encoding double-encodes any byte above
0x7F (`chr(147).encode("utf-8")` -> `b"\\xc2\\x93"`, corrupting the CLR
code), so PetsciiIO (io.py) is binary throughout and these constants are
already the exact bytes meant to hit the wire.

Unlike ANSI, PETSCII has NO escape sequences — every one of these is a
single control byte, confirmed directly against Synchronet's own CTerm
manual ("no escape sequences are used; all operations are performed via
single-byte control codes in CTerm's PETSCII mode"). There is also no
absolute cursor positioning in raw PETSCII (only HOME + single-step
movement) — renderer.py deliberately doesn't build a move(row, col)
primitive around these; see its module docstring.
"""

CLR = bytes([147])
HOME = bytes([19])

CURSOR_UP = bytes([145])
CURSOR_DOWN = bytes([17])
CURSOR_LEFT = bytes([157])
CURSOR_RIGHT = bytes([29])

REVERSE_ON = bytes([18])
REVERSE_OFF = bytes([146])

INSERT = bytes([148])
DELETE = bytes([20])
RETURN = bytes([13])

SWITCH_TO_LOWERCASE = bytes([14])  # enables true lowercase letters — see io.py
SWITCH_TO_UPPERCASE = bytes([142])

# ── Colors ───────────────────────────────────────────────────────────────
# Named to match renderers/ansi/ansi_codes.py's palette roles, so the two
# renderers stay easy to compare side by side: CYAN for field labels,
# YELLOW for shortcuts/highlights, WHITE for values, RED for errors.
BLACK = bytes([144])
WHITE = bytes([5])
RED = bytes([28])
CYAN = bytes([159])
PURPLE = bytes([156])
GREEN = bytes([30])
BLUE = bytes([31])
YELLOW = bytes([158])
ORANGE = bytes([129])
BROWN = bytes([149])
LIGHT_RED = bytes([150])
DARK_GREY = bytes([151])
MEDIUM_GREY = bytes([152])
LIGHT_GREEN = bytes([153])
LIGHT_BLUE = bytes([154])
LIGHT_GREY = bytes([155])
