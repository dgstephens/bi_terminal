#!/usr/bin/env python3
"""Offline PETSCII -> PNG preview renderer.

A local development/tuning tool, NOT part of the shipped door -- built
2026-08-13 so image_to_petscii_rows()'s actual output can be visually
compared directly against a source photo (or a real reference conversion,
like KTN_PETSCII.prg) without needing a live SyncTERM/Synchronet
connection for every single iteration. Reuses petscii_art.py's
compute_cell_grid() directly (the exact same per-cell decision function
the real door uses) -- this tool can never silently drift from what the
real door actually does, since it's not a reimplementation.

Requires two things NOT bundled in this repo, on purpose:

1. cbmcodecs2 (pip install cbmcodecs2) -- gives a well-tested, independent
   mapping from PETSCII CHR$ codes to real C64 "screen codes" (the
   different numbering scheme actually used to index into character ROM).
   Cross-checked against petscii_codes.py's CONFIRMED byte values while
   building this: e.g. byte 161 decodes to Unicode U+258C LEFT HALF BLOCK
   through this library, independently matching Daniel's own vimwiki note
   "left half colored, right half clear" -- real, independent
   confirmation the ground-truth data is correct.

2. A real C64 character ROM binary ("chargen") -- deliberately NOT
   bundled here: the real Commodore ROM is copyrighted, and even the free
   open-roms reverse-engineered replacement is a separate package with its
   own license/distribution terms, so bundling either in this git repo
   would be a real problem. Point --chargen at a local copy instead. VICE
   already needs one too, so if VICE is set up on this machine (see
   WriterDeck.wiki's VICE build notes), its own copy works directly and is
   used as the default search path below.

Usage:
    python3 scripts/petscii_preview.py path/to/image.jpg -o preview.png
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bi_terminal.renderers.petscii.petscii_art import _PALETTE, compute_cell_grid  # noqa: E402

CELL_PX = 8  # a C64 character cell is 8x8 pixels, natively
DEFAULT_SCALE = 4  # upscale factor so the output PNG is comfortably viewable

# VICE stores its ROM data under a per-platform subdirectory named after
# the emulated machine ("C64") -- these are the filenames VICE itself
# ships/downloads; any working chargen dump is fine, real Commodore ROM or
# open-roms.
_DEFAULT_CHARGEN_CANDIDATES = [
    Path.home() / ".local/share/vice/C64/chargen-901225-01.bin",
    Path.home() / ".local/share/vice/C64/chargen-906143-02.bin",
    Path("/usr/share/vice/C64/chargen-901225-01.bin"),
    Path("/usr/share/open-roms/chargen"),
]


def _find_default_chargen():
    for candidate in _DEFAULT_CHARGEN_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def _petscii_byte_to_screencode(n: int) -> int:
    """PETSCII CHR$ code -> real C64 screen code, via cbmcodecs2's
    independently-verified mapping (see this module's docstring). Charset
    (uc vs lc) doesn't matter for any byte value this tool actually
    renders -- confirmed empirically while building this: every glyph
    byte petscii_art.py can produce (space, quadrant/half/diagonal/dither
    block bytes) decodes to the IDENTICAL Unicode codepoint and screen
    code under both petscii_c64en_uc and petscii_c64en_lc, since the real
    door only ever uses this fixed image-glyph byte set, never letters."""
    import cbmcodecs2  # noqa: F401  (import registers the codecs)

    ch = bytes([n]).decode("petscii_c64en_uc")
    return ch.encode("screencode_c64_uc")[0]


def render_to_png(image_path: str, out_path: str, chargen_path: str, scale: int = DEFAULT_SCALE) -> None:
    from PIL import Image

    with open(chargen_path, "rb") as f:
        chargen = f.read()
    if len(chargen) < 2048:
        raise ValueError(f"{chargen_path} doesn't look like a valid chargen ROM ({len(chargen)} bytes, expected 4096)")

    color_lookup = {ctrl: rgb for rgb, ctrl in _PALETTE}
    screencode_cache = {}

    def screencode_for(glyph_byte):
        if glyph_byte not in screencode_cache:
            screencode_cache[glyph_byte] = _petscii_byte_to_screencode(glyph_byte)
        return screencode_cache[glyph_byte]

    src = Image.open(image_path).convert("RGB")
    w, h, grid = compute_cell_grid(src)

    out = Image.new("RGB", (w * CELL_PX * scale, h * CELL_PX * scale), (0, 0, 0))
    px = out.load()

    for y in range(h):
        for x in range(w):
            glyph, reverse, color = grid[y][x]
            glyph_byte = glyph[0]
            sc = screencode_for(glyph_byte)
            bitmap = chargen[sc * 8 : sc * 8 + 8]
            fg = color_lookup.get(color, (255, 255, 255)) if color is not None else (255, 255, 255)
            bg = (0, 0, 0)
            if reverse:
                fg, bg = bg, fg
            for row_i, row_byte in enumerate(bitmap):
                py0 = (y * CELL_PX + row_i) * scale
                for bit in range(8):
                    lit = bool(row_byte & (1 << (7 - bit)))
                    c = fg if lit else bg
                    px0 = (x * CELL_PX + bit) * scale
                    for dy in range(scale):
                        for dx in range(scale):
                            px[px0 + dx, py0 + dy] = c

    out.save(out_path)
    print(f"{w}x{h} cells -> {out.width}x{out.height} px -> {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", help="Path to a local JPG/PNG to convert")
    parser.add_argument("-o", "--output", default="petscii_preview.png", help="Output PNG path")
    parser.add_argument("--chargen", default=None, help="Path to a C64 character ROM binary")
    parser.add_argument("--scale", type=int, default=DEFAULT_SCALE, help="Pixel upscale factor")
    args = parser.parse_args()

    chargen_path = args.chargen or _find_default_chargen()
    if chargen_path is None:
        parser.error(
            "No chargen ROM found -- pass --chargen explicitly. "
            "VICE's own copy (see WriterDeck.wiki) works: "
            "~/.local/share/vice/C64/chargen-901225-01.bin"
        )

    render_to_png(args.image, args.output, str(chargen_path), scale=args.scale)


if __name__ == "__main__":
    main()
