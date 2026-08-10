"""ANSI CSI escape-code helpers for the generic ANSI door renderer.

Pure string-building — no I/O here, see io.py for the actual read/write
layer. 16-color palette (aixterm bright codes 90-97/100-107 for
portability), mapped against the existing retro theme
(renderers/textual/css.py) — those hex values are themselves standard
16-color values, confirming the whole app was already designed around this
palette:
  navy background  (#000080)  -> blue background          (44)
  cyan labels      (#55ffff)  -> bright cyan foreground    (96)
  yellow highlight (#ffff55)  -> bright yellow foreground  (93)
  white text       (#ffffff)  -> bright white foreground   (97)
  dim/hint text    (#5555aa)  -> blue foreground           (34)
  red (errors)     (#ff5555)  -> bright red foreground     (91)
"""

CSI = "\x1b["

RESET = CSI + "0m"
CLEAR_SCREEN = CSI + "2J" + CSI + "H"
CLEAR_LINE = CSI + "2K"
HIDE_CURSOR = CSI + "?25l"
SHOW_CURSOR = CSI + "?25h"

# Named colors matching the retro theme — see module docstring.
NAVY_BG = 44
CYAN = 96
YELLOW = 93
WHITE = 97
DIM = 34
RED = 91


def move(row: int, col: int = 1) -> str:
    return f"{CSI}{row};{col}H"


def sgr(*codes: int) -> str:
    """Select Graphic Rendition — combine multiple codes, e.g.
    sgr(NAVY_BG, WHITE) for white text on a navy background."""
    return f"{CSI}{';'.join(str(c) for c in codes)}m"


# The screen's persistent "base" state (navy background, white text) — real,
# live-reported bug (2026-08-10): NAVY_BG was defined above but never
# actually emitted anywhere in renderer.py, so the screen just showed
# whatever the caller's own terminal default background was, not the
# intended retro navy. Two things had to change together to fix this, not
# just "emit it once": (1) _header() emits BASE_SGR before CLEAR_SCREEN, so
# the freshly-erased area actually gets painted with navy -- a real
# terminal fills an erased region using whatever background is CURRENTLY
# ACTIVE at the moment of the erase, not some later color; (2) colored()
# below now returns to BASE_SGR instead of doing a hard RESET after each
# span -- a hard 0m reset would drop back to the terminal's own default
# background (usually black) for everything from that point on, since SGR
# state persists until explicitly changed, leaving the screen looking
# "patchy" (navy only until the very first colored label, black after).
# RESET itself is still exported/used once, deliberately, for the door's
# actual exit message (see renderers/ansi/app.py) — the user's own terminal
# shouldn't stay tinted navy after they disconnect from the door.
BASE_SGR = sgr(NAVY_BG, WHITE)


def colored(text: str, *codes: int) -> str:
    """Wrap `text` in the given SGR codes, returning to the screen's base
    navy-background state immediately after (not a hard reset — see
    BASE_SGR above)."""
    return f"{sgr(*codes)}{text}{BASE_SGR}"
