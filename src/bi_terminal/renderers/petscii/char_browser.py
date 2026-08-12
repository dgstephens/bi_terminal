"""PETSCII character browser — a live ground-truth tool, not part of the
normal Binventory door flow.

Built 2026-08-12 after the tiered-detail image experiment (petscii_art.py,
commit 87b875a) shipped a guessed byte value for a "shading" glyph
(petscii_codes.py's MEDIUM_SHADE = 166) that turned out wrong on a real
screen — Daniel live-reported it as "a black dither pattern," not a shade
blend. That confirmed what petscii_codes.py's own comment already flagged:
multiple sources (Wikipedia fetched twice, sta.c64.org fetched twice, a
real PETSCII-mapping Rust library) gave genuinely CONTRADICTORY byte values
for PETSCII's block/shading graphic characters, some conflating C64 "screen
codes" (direct memory POKE values) with actual PETSCII/CHR$ codes. No
amount of further research resolves that — it needs a real PETSCII-aware
client (SyncTERM) actually displaying each byte value so a human can read
off what glyph it produces. This tool does exactly that: pages through
every byte value NOT already known to be a control code, labels each with
its decimal value in plain (uppercase-only) ASCII, and lets the byte itself
render as whatever glyph it actually is on the connected client.

Deliberately excludes PETSCII's two known control-code ranges (0-31 and
128-159 — every currently-named constant in petscii_codes.py falls in one
of these two ranges, none outside them) rather than trying to send literal
byte values there: an unknown control code mid-grid could clear the screen,
move the cursor, or toggle reverse video and corrupt that page's layout.
Not dangerous (every page is a full CLR+redraw, so a glitch never persists
past the next keypress) but pointless — those two ranges are exhaustively
already-understood control codes, not unidentified glyphs, so browsing them
would show noise, not information. Also builds the excluded set from
petscii_codes.py's actual constants (not just the two hardcoded ranges) as
cheap future-proofing in case a later control code ever gets added outside
that pattern.

Deliberately standalone, not built on PetsciiRenderer/AppDriver at all: no
login, no FormSpec/ListPickerSpec, no Binventory API client, no
~/.binventory/config.json access whatsoever (see entry_petscii_charbrowser.py).
This is a pure diagnostic loop over PetsciiIO — the smallest possible
surface, on purpose, since its only job is "show me what byte N looks
like," not anything Binventory-specific.

UI text in this module intentionally bypasses sanitize.py's
to_petscii_text()/swapcase() — that swap exists to counteract
PetsciiRenderer's permanent switch to PETSCII charset 2 at startup, which
this tool does NOT do by default (starts in charset 1, the "graphics"
charset, since that's traditionally where PETSCII's block/shading
characters live and is the more likely home for what Daniel's hunting for
— toggle to charset 2 with 'C' to check there too). All UI text here is
plain uppercase-only ASCII written directly, which displays correctly
un-swapped in charset 1. Toggling to charset 2 will flip this tool's own
labels to display in lowercase (PETSCII charset 2's real, well-documented
case inversion) — still fully readable, just not uppercase anymore; not a
bug, not worth suppressing for a one-off diagnostic screen.
"""

from typing import List

from . import petscii_codes as pc
from .io import PetsciiIO

# PETSCII's two well-established control-code ranges (see this module's
# docstring) — every currently-named control constant in petscii_codes.py
# falls inside one of these two (confirmed by this module's own tests), so
# excluding the ranges wholesale is sufficient on its own.
_CONTROL_RANGES = (range(0, 32), range(128, 160))

# Named byte constants that fall INSIDE those control ranges — built
# dynamically (not hardcoded) purely as future-proofing, so a future new
# control-code constant added to petscii_codes.py is automatically excluded
# here too without needing this file edited in lockstep. Deliberately
# intersected with _CONTROL_RANGES rather than including every named
# constant unconditionally: petscii_codes.py also defines
# LEFT_HALF_BLOCK/LOWER_HALF_BLOCK/MEDIUM_SHADE/RIGHT_HALF_BLOCK, which are
# UNVERIFIED GLYPH GUESSES living at 161/162/166/167 (outside both control
# ranges) — exactly the kind of byte this browser exists to check, not a
# control code to hide. Treating every named constant as "known control"
# unconditionally was a real bug caught by this module's own test suite: it
# silently excluded those four candidates from the browse set entirely.
KNOWN_CONTROL_BYTES = {
    getattr(pc, name)[0]
    for name in dir(pc)
    if not name.startswith("_") and isinstance(getattr(pc, name), bytes) and len(getattr(pc, name)) == 1
} & set().union(*_CONTROL_RANGES)


def _is_control_byte(n: int) -> bool:
    return n in KNOWN_CONTROL_BYTES or any(n in r for r in _CONTROL_RANGES)


PRINTABLE_CANDIDATES: List[int] = [n for n in range(0, 256) if not _is_control_byte(n)]

COLUMNS = 6
ROWS_PER_PAGE = 10
PAGE_SIZE = COLUMNS * ROWS_PER_PAGE


def _raw(text: str) -> bytes:
    """Plain ASCII encode, no substitution table, no case swap -- see this
    module's docstring for why to_petscii_text() doesn't apply here. Every
    caller in this module passes pure-ASCII literals it wrote itself (no
    user-supplied/backend text ever reaches this tool), so a plain
    ascii-strict encode is correct and simpler than reusing the
    general-purpose sanitizer built for different, less-controlled input."""
    return text.encode("ascii")


def paginate(candidates: List[int], page_size: int = PAGE_SIZE) -> List[List[int]]:
    """Split *candidates* into fixed-size pages -- a pure function so the
    chunking logic is testable without a real/fake PetsciiIO at all."""
    return [candidates[i : i + page_size] for i in range(0, len(candidates), page_size)]


def render_page_rows(byte_values: List[int], columns: int = COLUMNS) -> List[bytes]:
    """One bytes chunk per row: each cell is a 3-digit decimal label, a
    colon, the raw candidate byte itself (whatever glyph it turns out to
    be), and a trailing space -- 6 bytes per cell, so `columns=6` fits
    within PETSCII's 40-column screen (36 of 40) with a few columns to
    spare. A pure function, same testability reasoning as paginate()."""
    rows = []
    for i in range(0, len(byte_values), columns):
        row = bytearray()
        for n in byte_values[i : i + columns]:
            row += _raw(f"{n:3d}:")
            row += bytes([n])
            row += _raw(" ")
        rows.append(bytes(row))
    return rows


def build_page_lines(page_idx: int, total_pages: int, charset: int, byte_values: List[int]) -> List[bytes]:
    """Every line of one full page (header + glyph rows + footer), NOT
    including CLR or trailing RETURNs -- the caller adds those, same
    "conversion doesn't own display/pacing concerns" split petscii_art.py's
    image_to_petscii_rows() already uses. A pure function, same
    testability reasoning as paginate()/render_page_rows()."""
    lines = [
        _raw(f"PETSCII CHAR BROWSER - CHARSET {charset}"),
        _raw(f"PAGE {page_idx + 1} OF {total_pages}  ({len(PRINTABLE_CANDIDATES)} BYTES TOTAL)"),
        b"",
    ]
    lines.extend(render_page_rows(byte_values))
    lines.append(b"")
    lines.append(_raw("[N]EXT [B]ACK [C]HARSET [Q]UIT"))
    return lines


def run(io: PetsciiIO) -> None:
    """The interactive browse loop. Blocking, returns when the caller quits
    (Q/Escape/Ctrl+C) -- same "run until done" shape as PetsciiApp.run(),
    just with no AppDriver/screen-stack underneath it.

    Real, live-reported bug (2026-08-12): the first version of this loop
    wrote CLR then every line as its own immediate write_raw()+flush() call
    in a tight loop, no pacing at all -- Daniel's connection disconnected
    immediately after the FIRST page rendered, before he ever got to press
    a key. Exactly the same failure shape already root-caused and fixed
    once this same day for PETSCII image display (renderer.py's
    show_image(): a burst of many unpaced writes, each full of raw control-
    range-adjacent bytes, overwhelms/races the connected client's terminal
    processing) -- that fix (io.write_rows_paced(), one write+flush+small
    delay per row) just hadn't been carried over to this newer tool yet.
    Applying the same proven pattern here instead of re-deriving a new one."""
    pages = paginate(PRINTABLE_CANDIDATES)
    page_idx = 0
    charset = 1  # 1 = default "graphics" charset, 2 = SWITCH_TO_LOWERCASE's "text" charset
    while True:
        io.write_raw(pc.CLR)
        lines = build_page_lines(page_idx, len(pages), charset, pages[page_idx])
        io.write_rows_paced([line + b"\r" for line in lines])

        key = io.read_key()
        # Real, live-reported bug (2026-08-12): a real PETSCII keyboard
        # (via SyncTERM) sends an unshifted letter key's ASCII-UPPERCASE
        # byte value regardless of which charset is currently displayed --
        # confirmed straight from the debug log: pressing the physical 'q'
        # key logged as `raw=0x51 (81) -> 'Q'`, not lowercase 'q'. Charset
        # only changes how a byte gets DRAWN on screen, not what the
        # keyboard sends for it -- same real hardware behavior this
        # project's sanitize.py already documents for OUTPUT text, just
        # never accounted for on the INPUT side here. Every single-letter
        # comparison below was checking only the lowercase form, so N/B/C/Q
        # never matched anything and just silently redrew the same page --
        # exactly the reported symptom. show_confirm() elsewhere in this
        # same renderer already guards against this (`key.lower() == "y"`);
        # this loop just hadn't followed that same established pattern.
        key = key.lower() if key else key
        if key in ("q", "escape", "ctrl+c"):
            return
        if key in ("n", "enter", "right", " "):
            page_idx = (page_idx + 1) % len(pages)
            continue
        if key in ("b", "left"):
            page_idx = (page_idx - 1) % len(pages)
            continue
        if key == "c":
            charset = 2 if charset == 1 else 1
            io.write_raw(pc.SWITCH_TO_LOWERCASE if charset == 2 else pc.SWITCH_TO_UPPERCASE)
            continue
        # any other key (including None on timeout) -- ignore, redraw same page
