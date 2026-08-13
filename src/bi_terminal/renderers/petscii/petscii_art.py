"""PIL -> PETSCII color-block art conversion.

Real PETSCII image support, built 2026-08-11 in response to a direct
question: SyncTERM/Synchronet's own documentation genuinely supports
ANSI/PETSCII graphics, so "why doesn't this door do it" deserved a real
answer, not "it's impossible" — it wasn't impossible, just not built yet
(image_capability was deliberately left at NONE with a note that
PETSCII_GRAPHICS was reserved for exactly this).

Two real protocol constraints shape the approach here, both already
established by this project's own prior PETSCII research (see
petscii_codes.py's module docstring) and reconfirmed while researching
this specifically:

1. PETSCII has no remote background-color control code at all — only a
   per-character FOREGROUND color plus REVERSE_ON/OFF to swap a
   character's own fg/bg against the (locally fixed, not remotely
   settable) screen background. This means, unlike the ANSI door's
   half-block art (renderers/_shared_ansi_art.py, which sets independent
   foreground AND background colors per character cell to get 2x vertical
   resolution from ▄), a PETSCII character cell only ever has ONE
   effective controllable color. There is no equivalent trick available —
   this is a genuine, confirmed hardware/protocol constraint, not a gap
   in this implementation.

2. The 16-color palette is fixed hardware, not arbitrary RGB. Values below
   are Philip "Pepto" Timmermann's well-known, widely-cited measured VIC-II
   palette (see http://www.pepto.de/projects/colorvic/) — the same
   reference this project already used when picking petscii_codes.py's
   color names in the first place. Every source pixel gets quantized to
   its nearest (least-squared RGB distance) match among these 16.

Quadrant-glyph mode (2026-08-13), replacing the original flat "one solid
color per cell" v1 approach entirely — this is what Daniel originally asked
for back on 2026-08-12 ("reduce the image to 2x columns x 2x rows... so
each PETSCII character is actually 4 pixels — 2 horizontal, 2 vertical")
and what an EARLIER same-day attempt (petscii_art.py commit 87b875a,
reverted) tried and got visibly wrong, for two compounding reasons: it only
ever sub-sampled horizontally (never touched vertical resolution at all),
and it used guessed byte values for the "shading" glyph that turned out
flatly wrong on a real screen. Both are fixed now: real vertical
sub-sampling below, and the glyph bytes come from petscii_codes.py's
CONFIRMED section — Daniel actually paged through every PETSCII byte value
on a real SyncTERM connection (renderers/petscii/char_browser.py) and
hand-recorded what each one looks like.

Each character cell now samples a 2x2 grid of sub-pixels (top-left,
top-right, bottom-left, bottom-right). Each sub-pixel is independently
quantized against the 16-color palette; one that quantizes to BLACK is
treated as "off" (shows through as whatever the local terminal background
already is, exactly like a plain unreversed space already does — no new
concept, just applying the existing quantization result instead of always
painting black as a literal drawn color) and everything else as "on."
Since a PETSCII cell only ever has ONE controllable color (constraint #1
above), all "on" sub-pixels get averaged into a single representative
color for the whole cell, then that average is itself quantized to the
nearest palette entry.

Which of the 16 possible on/off patterns get an EXACT confirmed glyph
match, and which have to round up to a plain solid block instead, is a
direct, honest consequence of what's actually confirmed to exist in
PETSCII's character ROM (petscii_codes.py's CONFIRMED section) — not an
implementation gap. Checked BEFORE any of this, though: if the "on"
sub-pixels show SIGNIFICANT real color variance (squared RGB distance
above _DITHER_VARIANCE_THRESHOLD, e.g. fur vs. background, not just a
shape edge against black), a dither/checkerboard glyph is used instead of
any shape match — added 2026-08-13 after Daniel live-noticed "no dithered
blocks" ever appeared despite the confirmed DITHER_BLOCK_* constants
existing (they'd been transcribed into petscii_codes.py but never
actually wired into this decision logic), then retuned the same day after
the first version over-corrected: comparing QUANTIZED colors instead of
actual RGB distance fired dither on ordinary photographic noise that
happened to cross a palette-quantization boundary, not just real color
transitions — "a lot of dithering going on... too much, really." Color
variance takes priority over shape matching because a shape glyph can
only ever show ONE color anyway, so picking one and silently discarding
the other(s) is worse than a texture that at least signals "mixed content
here."
  - 0 on  -> plain space (shows background)
  - on sub-pixels show significant real color variance -> a dither glyph
             (color variance beats shape matching, checked first)
  - 1 on  -> the matching QUADRANT_* corner glyph (all 4 confirmed)
  - 2 on  -> LEFT_HALF_BLOCK / LOWER_HALF_BLOCK / QUADRANT_DIAGONAL_TL_BR
             for the 3 of 6 possible two-corner combinations Daniel's real
             character-browser survey actually found a glyph for; the
             other 3 (top half, right half, the other diagonal) genuinely
             don't appear anywhere in that survey of the full non-control
             byte range, so they're very likely just not in the ROM at
             all, not merely "not found yet" — those round up to a solid
             block rather than guess at an unconfirmed byte.
  - 3 on  -> no confirmed 3-quadrant glyph exists either -- rounds up to a
             solid block.
  - 4 on  -> solid block, the same REVERSE_ON+space "chunky pixel" trick
             v1 already used and Daniel already confirmed looks right.

REVERSE_ON/OFF is now embedded directly in each row's own bytes (state
tracked cell-by-cell, only emitted on an actual change, same run-length
idea already used for color) rather than the caller wrapping the whole row
externally — a genuine, deliberate contract change from the v1/tiered-
detail eras, made necessary because a single row can now freely mix
reversed (solid-block) and non-reversed (quadrant/half-glyph) cells, which
a single whole-row wrap could never express. See renderer.py's show_image
for the caller-side half of this change.
"""

from io import BytesIO
from typing import List, Optional, Tuple

from . import petscii_codes as pc

# Pepto's measured VIC-II palette, index-matched to petscii_codes.py's
# color control bytes below — see module docstring for the source.
_PALETTE: List[Tuple[Tuple[int, int, int], bytes]] = [
    ((0x00, 0x00, 0x00), pc.BLACK),
    ((0xFF, 0xFF, 0xFF), pc.WHITE),
    ((0x68, 0x37, 0x2B), pc.RED),
    ((0x70, 0xA4, 0xB2), pc.CYAN),
    ((0x6F, 0x3D, 0x86), pc.PURPLE),
    ((0x58, 0x8D, 0x43), pc.GREEN),
    ((0x35, 0x28, 0x79), pc.BLUE),
    ((0xB8, 0xC7, 0x6F), pc.YELLOW),
    ((0x6F, 0x4F, 0x25), pc.ORANGE),
    ((0x43, 0x39, 0x00), pc.BROWN),
    ((0x9A, 0x67, 0x59), pc.LIGHT_RED),
    ((0x44, 0x44, 0x44), pc.DARK_GREY),
    ((0x6C, 0x6C, 0x6C), pc.MEDIUM_GREY),
    ((0x9A, 0xD2, 0x84), pc.LIGHT_GREEN),
    ((0x6C, 0x5E, 0xB5), pc.LIGHT_BLUE),
    ((0x95, 0x95, 0x95), pc.LIGHT_GREY),
]

GRID_WIDTH = 38
"""Leaves a 1-column margin either side of the 40-column PETSCII screen —
matches renderer.py's own _WIDTH=39 convention (its own margin choice)
closely enough to look consistent without needing to import across
modules for one constant."""

SPACE = bytes([32])

# Confirmed glyph lookup tables (petscii_codes.py's CONFIRMED section) —
# keyed by (top_left, top_right, bottom_left, bottom_right) on/off pattern.
# See this module's docstring for why only these particular patterns have
# an exact match.
_ONE_ON_GLYPHS = {
    (True, False, False, False): pc.QUADRANT_TOP_LEFT,
    (False, True, False, False): pc.QUADRANT_TOP_RIGHT,
    (False, False, True, False): pc.QUADRANT_BOTTOM_LEFT,
    (False, False, False, True): pc.QUADRANT_BOTTOM_RIGHT,
}
_TWO_ON_GLYPHS = {
    (True, False, True, False): pc.LEFT_HALF_BLOCK,  # top-left + bottom-left
    (False, False, True, True): pc.LOWER_HALF_BLOCK,  # bottom-left + bottom-right
    (True, False, False, True): pc.QUADRANT_DIAGONAL_TL_BR,  # top-left + bottom-right
}


def _nearest_color(rgb: Tuple[int, int, int]) -> bytes:
    best = min(_PALETTE, key=lambda entry: sum((a - c) ** 2 for a, c in zip(entry[0], rgb)))
    return best[1]


def _rgb_distance(a: Tuple[int, int, int], b: Tuple[int, int, int]) -> int:
    return sum((x - y) ** 2 for x, y in zip(a, b))


# Real, live-reported bug (2026-08-13): comparing a real reference PETSCII
# conversion of the same photo against our own output, Daniel confirmed
# "it's definitely got a lot of dithering going on. I think too much,
# really." Root cause: dithering was triggered by comparing QUANTIZED
# colors ("do these on-pixels round to two different palette entries at
# all") rather than the actual underlying RGB distance -- on a real,
# noisy photo, two visually near-identical sub-pixels constantly land on
# opposite sides of a palette quantization boundary (ordinary photographic
# sensor/JPEG noise, not a real color difference), which fired dither
# almost everywhere instead of just genuine edges/color transitions. A
# squared-RGB-distance threshold on the ORIGINAL (pre-quantization) colors
# is a much better proxy for "is this actually two different colors."
# 4000 (~36 per channel average) is a first-pass tuned guess, not
# independently confirmed -- picked to comfortably exceed ordinary
# photographic noise while still catching a real transition between two
# different palette-scale colors; expect to retune from Daniel's next live
# look, the same iterative process this file's whole history has followed.
_DITHER_VARIANCE_THRESHOLD = 4000


def _has_significant_color_variance(pixels: List[Tuple[int, int, int]]) -> bool:
    for i in range(len(pixels)):
        for j in range(i + 1, len(pixels)):
            if _rgb_distance(pixels[i], pixels[j]) > _DITHER_VARIANCE_THRESHOLD:
                return True
    return False


def _average_color(pixels: List[Tuple[int, int, int]]) -> bytes:
    n = len(pixels)
    avg = tuple(sum(p[i] for p in pixels) / n for i in range(3))
    return _nearest_color(avg)


def _quadrant_cell(
    top_left: Tuple[int, int, int],
    top_right: Tuple[int, int, int],
    bottom_left: Tuple[int, int, int],
    bottom_right: Tuple[int, int, int],
) -> Tuple[bytes, bool, Optional[bytes]]:
    """Decide one cell's (glyph, reverse, color) from its 4 sampled
    sub-pixels. `color` is None only when the cell is fully "off" (nothing
    to draw, no color change needed) -- see this module's docstring for the
    on/off/glyph-selection rules."""
    corners = (top_left, top_right, bottom_left, bottom_right)
    quantized = [_nearest_color(c) for c in corners]
    pattern = tuple(q != pc.BLACK for q in quantized)
    on_pixels = [c for c, on in zip(corners, pattern) if on]
    count = len(on_pixels)
    if count == 0:
        return SPACE, False, None
    color = _average_color(on_pixels)
    if count >= 2 and _has_significant_color_variance(on_pixels):
        # Real, live-reported observation (2026-08-13): "no dithered
        # blocks" ever appeared, because nothing in this function ever
        # selected one -- petscii_codes.py's DITHER_BLOCK_* constants were
        # transcribed from Daniel's real character-browser notes but never
        # actually wired into this decision logic. Fixed the same day, then
        # immediately over-corrected: the first version compared QUANTIZED
        # colors ("do these on-pixels round to two different palette
        # entries at all"), which on a real noisy photo fired dither almost
        # everywhere -- Daniel: "it's definitely got a lot of dithering
        # going on. I think too much, really." Comparing actual RGB
        # distance on the ORIGINAL colors (_has_significant_color_variance)
        # instead means ordinary photographic noise that happens to cross a
        # quantization boundary no longer triggers dither, only genuine
        # color transitions do (e.g. fur vs. background, not fur vs.
        # slightly-different-shade-of-the-same-fur). Checked BEFORE the
        # count-based shape matching below on purpose: even a pattern that
        # WOULD have an exact confirmed shape glyph (e.g. LEFT_HALF_BLOCK)
        # can only ever show ONE color anyway, so real color variance takes
        # priority over shape matching, not the reverse. Which of the 5
        # confirmed "full block dither" byte variants gets used doesn't
        # meaningfully matter -- Daniel's notes describe them as
        # near-identical (only which corner pixel is clear/colored
        # differs) -- so one (DITHER_BLOCK_166) is picked consistently
        # rather than cycled.
        return pc.DITHER_BLOCK_166, False, color
    if count == 1:
        return _ONE_ON_GLYPHS[pattern], False, color
    if count == 2 and pattern in _TWO_ON_GLYPHS:
        return _TWO_ON_GLYPHS[pattern], False, color
    # count == 4, or count in (2, 3) with no confirmed exact glyph -- round
    # up to a solid block rather than guess at an unconfirmed byte.
    return SPACE, True, color


def image_to_petscii_rows(url: str) -> Optional[List[bytes]]:
    """Download *url* and return one bytes chunk per image row, each
    ending in RETURN and fully self-contained (including its own
    REVERSE_ON/OFF toggling -- see this module's docstring), or None on any
    failure -- matching _shared_ansi_art.py's image_to_renderable()
    contract (a renderer should never crash on a bad/unreachable image
    URL, just skip rendering it).

    Returns a LIST rather than one concatenated bytes blob so the caller
    (renderer.py's show_image) can write/flush/pace each row individually
    -- a real, live-reported bug (2026-08-12): a single large burst write
    showed only the image's first row through an actual Synchronet
    connection."""
    if not url:
        return None
    try:
        import requests
        from PIL import Image

        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content)).convert("RGB")

        w = GRID_WIDTH
        aspect = img.height / img.width
        # Terminal character cells are roughly twice as tall as they are
        # wide (matches the C64's own 8x8 cell on a 320x200-over-4:3
        # display) -- halving the naive aspect-derived row count corrects
        # for that. This formula is UNCHANGED from v1 despite now sampling
        # a 2x2 sub-pixel grid per cell instead of one sample per cell: each
        # sub-pixel inherits the same ~1:2 width:height proportions as the
        # whole cell (a cell split into 2x2 sub-regions keeps that same
        # aspect at the sub-region level), so the correction factor that
        # applied to the whole sample grid before still applies the same
        # way now -- only the SAMPLING resolution changes (w*2 x h*2
        # instead of w x h), not this row-count formula.
        h = max(1, int(w * aspect * 0.5))
        img = img.resize((w * 2, h * 2))

        rows = []
        current_color = None
        for y in range(h):
            row = bytearray()
            current_reverse = False
            for x in range(w):
                top_left = img.getpixel((x * 2, y * 2))
                top_right = img.getpixel((x * 2 + 1, y * 2))
                bottom_left = img.getpixel((x * 2, y * 2 + 1))
                bottom_right = img.getpixel((x * 2 + 1, y * 2 + 1))
                glyph, reverse, color = _quadrant_cell(top_left, top_right, bottom_left, bottom_right)
                if reverse != current_reverse:
                    row += pc.REVERSE_ON if reverse else pc.REVERSE_OFF
                    current_reverse = reverse
                if color is not None and color != current_color:
                    row += color
                    current_color = color
                row += glyph
            if current_reverse:
                row += pc.REVERSE_OFF  # never leave a row still in reverse mode
            row += pc.RETURN
            rows.append(bytes(row))
        return rows
    except Exception:
        return None
