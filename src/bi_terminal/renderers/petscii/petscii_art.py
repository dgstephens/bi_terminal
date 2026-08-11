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
   in this implementation. The one real trick PETSCII *does* offer:
   REVERSE_ON turns a plain space into a solid block of the current
   foreground color (space has no glyph pixels, so reversing it paints
   the whole cell) — that's the basis for the "chunky pixel" mosaic
   approach below: one solid-colored block per character cell.

2. The 16-color palette is fixed hardware, not arbitrary RGB. Values below
   are Philip "Pepto" Timmermann's well-known, widely-cited measured VIC-II
   palette (see http://www.pepto.de/projects/colorvic/) — the same
   reference this project already used when picking petscii_codes.py's
   color names in the first place. Every source pixel gets quantized to
   its nearest (least-squared RGB distance) match among these 16.
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


def _nearest_color(rgb: Tuple[int, int, int]) -> bytes:
    r, g, b = rgb
    best = min(_PALETTE, key=lambda entry: sum((a - c) ** 2 for a, c in zip(entry[0], rgb)))
    return best[1]


def image_to_petscii_bytes(url: str) -> Optional[bytes]:
    """Download *url* and return a ready-to-write PETSCII byte sequence (a
    grid of solid-colored character cells approximating the image), or
    None on any failure — matching _shared_ansi_art.py's
    image_to_renderable() contract (a renderer should never crash on a
    bad/unreachable image URL, just skip rendering it)."""
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
        # for that, the same class of correction _shared_ansi_art.py's
        # "ansi" mode gets for free from its half-block trick (2 image
        # rows per character row) but must be done explicitly here since a
        # PETSCII cell only ever represents ONE image sample, not two.
        h = max(1, int(w * aspect * 0.5))
        img = img.resize((w, h))

        out = bytearray()
        out += pc.REVERSE_ON
        current_color = None
        for y in range(h):
            for x in range(w):
                color = _nearest_color(img.getpixel((x, y)))
                if color != current_color:
                    out += color
                    current_color = color
                out += SPACE
            out += pc.RETURN
        out += pc.REVERSE_OFF
        return bytes(out)
    except Exception:
        return None
