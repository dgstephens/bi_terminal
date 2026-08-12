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

No screen/border background color control code exists in this table at all
(confirmed against sta.c64.org's full control-code list, live-checked again
2026-08-10 in response to a "why isn't the background blue like ANSI"
report) — only per-character FOREGROUND colors (below) plus REVERSE_ON/OFF
to swap a character's own fg/bg. On real hardware, screen/border background
is a POKE to a memory-mapped hardware register (53280/53281), not a byte a
remote program can send down a serial/modem link — this is a genuine C64
protocol limit, not a gap in this renderer. Whatever background a caller
sees is just whatever their own terminal software (SyncTERM, etc.) already
had set locally before connecting; this door has no way to change it.
ansi_codes.py's NAVY_BG (SGR 44) has no PETSCII equivalent for this reason.
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

# ── Block/shading graphic characters (CONFIRMED 2026-08-12) ─────────────────
# Ground truth, not guesses: Daniel built and ran renderers/petscii/
# char_browser.py (a diagnostic door that pages through every PETSCII byte
# value, labeled with its decimal number) over a real SyncTERM connection
# and hand-recorded what every graphic byte actually looks like, in
# ~/vimwiki/Binventory/TestingPETSCIIChars.wiki. This section replaces the
# previous guessed values, which came from contradictory secondary sources
# (Wikipedia/sta.c64.org/a Rust PETSCII library all disagreed) and were
# never independently confirmed -- two of the four were wrong: MEDIUM_SHADE
# (166) is NOT a medium/uniform shade at all, it's a checkerboard dither
# block with one corner pixel different (exactly matching Daniel's real
# live report on the reverted tiered-detail experiment: "a black dither
# pattern on entire blocks of color"), and RIGHT_HALF_BLOCK (167) is not a
# half-block at all -- it's a single-pixel-wide vertical line at the far
# right edge. LEFT_HALF_BLOCK (161) and LOWER_HALF_BLOCK (162) were the two
# guesses that turned out correct, confirmed here rather than assumed.
#
# Every constant below is named for what Daniel actually saw, byte value
# preserved from his notes. Several entries have very similar descriptions
# (e.g. 126/166/222/230/255 are all "full block dither, one corner
# clear/colored") -- real, plausible distinct ROM glyphs (the character ROM
# is known to include multiple checkerboard/dither variants), not assumed
# duplicates, so each keeps its own name with the byte value baked in
# rather than inventing a semantic distinction that isn't actually
# confirmed. Deliberately excludes byte values that are just ordinary
# already-known ASCII punctuation Daniel also tested for image-art texture
# use (40 "(", 41 ")", 60 "<", 62 ">", 64 "@", 91 "[", 93 "]") -- those need
# no new constant, they're already producible as plain text.

# Half-blocks -- the two most directly useful for "chunky pixel" mosaic
# art, since REVERSE_ON+space already gives a full solid block.
LEFT_HALF_BLOCK = bytes([161])  # left half colored, right half clear
LOWER_HALF_BLOCK = bytes([162])  # top half clear, bottom half colored

# Quadrant pieces -- fill exactly one quarter of the cell. The real
# building blocks for the "2x2 sub-pixel" quadrant-matching technique
# Daniel originally asked about; genuinely new information, not available
# in any of the earlier guessed constants.
QUADRANT_TOP_LEFT = bytes([190])
QUADRANT_TOP_RIGHT = bytes([188])
QUADRANT_BOTTOM_LEFT = bytes([187])
QUADRANT_BOTTOM_RIGHT = bytes([172])
QUADRANT_BOTTOM_RIGHT_255_VARIANT = bytes([236])  # "square block bottom right" -- Daniel logged this separately from 172
QUADRANT_DIAGONAL_TL_BR = bytes([191])  # top-left AND bottom-right quadrants both colored

# Dither/checkerboard blocks -- NOT a uniform medium-gray shade (that was
# the wrong assumption behind the old MEDIUM_SHADE name); each is a full
# block dither pattern with one specific corner pixel clear or colored.
DITHER_BLOCK_126 = bytes([126])  # full block dither, upper left corner clear
DITHER_BLOCK_166 = bytes([166])  # full block dither, upper left corner colored -- was wrongly named MEDIUM_SHADE
DITHER_BLOCK_222 = bytes([222])  # full block dither, top left pixel clear
DITHER_BLOCK_230 = bytes([230])  # full block dither, top left pixel colored
DITHER_BLOCK_255 = bytes([255])  # full block dither, top left clear
LEFT_HALF_DITHER = bytes([124])  # left half dither pattern
LEFT_HALF_DITHER_220 = bytes([220])  # 1/2 dither pattern left side, top left pixel white
BOTTOM_HALF_DITHER = bytes([168])  # top half clear, bottom half dither pattern
BOTTOM_HALF_DITHER_BR_COLORED = bytes([232])  # 1/2 dither pattern, bottom half, bottom right colored

# Thin bars/lines/quarter-bars -- edge/texture detail, thinner than a half
# block. Useful for future finer-grained edge detection, not the primary
# mosaic building blocks.
THIN_BAR_TOP = bytes([163])  # 1 pixel horizontal bar across the top
THIN_BAR_BOTTOM = bytes([164])  # 1 pixel horizontal bar across the bottom
QUARTER_BAR_LEFT = bytes([165])  # 1/4 vertical bar far left
THIN_BAR_RIGHT = bytes([167])  # 1 pixel vertical bar far right -- was wrongly named RIGHT_HALF_BLOCK, it's a thin line, not a half-width fill
QUARTER_BAR_RIGHT = bytes([170])  # 1/4 vertical bar far right
QUARTER_BAR_BOTTOM = bytes([175])  # 1/4 horizontal bar bottom
QUARTER_BAR_TOP = bytes([183])  # 1/4 horizontal bar top
THIN_BAR_LEFT = bytes([180])  # 1 pixel vertical bar far left
BAR_LEFT_2PX = bytes([181])  # 2 pixel vertical bar far left
BAR_RIGHT_2PX = bytes([182])  # 2 pixel vertical bar far right
BAR_TOP_2PX = bytes([184])  # 2 pixel horizontal bar top
BAR_BOTTOM_2PX = bytes([185])  # 2 pixel horizontal bar bottom
THIN_LINE_NEAR_BOTTOM = bytes([192])  # 1 pixel horizontal line 1 pixel from bottom
THIN_LINE_CENTER_VERTICAL = bytes([221])  # 1 pixel wide vertical line, center
LINE_LEFT_2PX = bytes([244])  # 2 pixel vertical line left
LINE_LEFT_3PX = bytes([245])  # 3 pixel vertical line left
LINE_RIGHT_3PX = bytes([246])  # 3 pixel vertical line right
LINE_TOP_1PX = bytes([247])  # 1 pixel horizontal line top
LINE_TOP_2PX = bytes([248])  # 2 pixel horizontal line top
LINE_BOTTOM_2PX = bytes([249])  # 2 pixel horizontal line bottom
THIN_BAR_BOTTOM_239 = bytes([239])  # 1 pixel horizontal bar bottom

# "Bar" variants of the half-blocks above -- Daniel logged these as
# distinct entries from 161/162, description worded slightly differently
# ("colored bar" vs "colored, ... clear") so kept separate rather than
# assumed identical.
LEFT_HALF_BAR = bytes([225])  # 1/2 colored bar left
BOTTOM_HALF_BAR = bytes([226])  # 1/2 colored bar bottom

# Diagonal patterns and other full-cell glyphs.
DIAGONAL_BARS_CLEAR_LR = bytes([127])  # 4 clear diagonal bars, left to right, top to bottom
DIAGONAL_BARS_CLEAR_RL = bytes([169])  # 4 clear diagonal bars, right to left, top to bottom
DIAGONAL_BARS_FILLED_TL_BR = bytes([223])  # 4 black diagonal lines, top left to bottom right
DIAGONAL_BARS_FILLED_TR_BL = bytes([233])  # 4 black diagonal lines, tip right to bottom left
PLUS_FULL_SIZE = bytes([123])  # a plus sign, but full character height and width
HORIZONTAL_LINE_FULL = bytes([96])  # not a dash -- a horizontal full-width line
