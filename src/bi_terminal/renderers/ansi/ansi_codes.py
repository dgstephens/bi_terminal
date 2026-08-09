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


def colored(text: str, *codes: int) -> str:
    """Wrap `text` in the given SGR codes, resetting immediately after."""
    return f"{sgr(*codes)}{text}{RESET}"
