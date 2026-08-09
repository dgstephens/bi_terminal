"""Reserved module: PIL -> ANSI-pixels / ASCII-art conversion, shared between
the Textual renderer's ansi/ascii image_mode and the future generic ANSI door
renderer (both target the same class of display — a truecolor-or-16-color
terminal — so there's no reason for the ANSI door to reimplement this from
scratch once it's built).

Intentionally empty for this increment. bi_python's `_image_to_renderable()`
(in forms.py) is the reference implementation to port here during the
Textual-renderer-rewrite phase (see README "Sequencing", step 3) — downloads
an image URL via `requests`, decodes via `PIL`, and converts to either a
`rich_pixels.Pixels` object (ansi mode) or an `ascii_magic` string (ascii
mode). Reserving the module/location now so that phase puts the conversion
code in the right place the first time, instead of writing it directly inside
renderers/textual/ and needing a later extraction to unblock the ANSI door.

PETSCII/ATASCII graphics conversion (C64 charset packing, Atari ANTIC/GTIA
modes) is NOT shared with this module — it's genuinely different code,
belonging in renderers/petscii/ and renderers/atascii/ respectively once that
work starts.
"""
