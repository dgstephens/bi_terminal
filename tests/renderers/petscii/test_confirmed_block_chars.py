"""Regression lock for petscii_codes.py's confirmed block/shading/graphic
character byte values.

These aren't guessed anymore (see petscii_codes.py's own "CONFIRMED
2026-08-12" section header) -- Daniel read them directly off a real
SyncTERM screen using renderers/petscii/char_browser.py and recorded them
in ~/vimwiki/Binventory/TestingPETSCIIChars.wiki. That was real,
non-repeatable effort (paging through a live connection, one screen at a
time); this test exists purely so a future accidental edit to
petscii_codes.py can't silently corrupt that data without a test failing.
Not testing anything about how these glyphs actually LOOK (a unit test
can't) -- only that the byte values match what was actually recorded.
"""

from bi_terminal.renderers.petscii import petscii_codes as pc


def test_half_blocks():
    assert pc.LEFT_HALF_BLOCK == bytes([161])
    assert pc.LOWER_HALF_BLOCK == bytes([162])


def test_previously_wrong_guesses_are_corrected():
    """The two guessed constants that turned out wrong (see
    petscii_art.py's reverted tiered-detail experiment) -- MEDIUM_SHADE and
    RIGHT_HALF_BLOCK no longer exist under those names at all, since both
    names described something the byte doesn't actually do. Byte 166 is
    now DITHER_BLOCK_166 (a checkerboard dither, not a uniform shade), and
    167 is THIN_BAR_RIGHT (a 1-pixel line, not a half-width fill)."""
    assert not hasattr(pc, "MEDIUM_SHADE")
    assert not hasattr(pc, "RIGHT_HALF_BLOCK")
    assert pc.DITHER_BLOCK_166 == bytes([166])
    assert pc.THIN_BAR_RIGHT == bytes([167])


def test_quadrant_pieces():
    assert pc.QUADRANT_TOP_LEFT == bytes([190])
    assert pc.QUADRANT_TOP_RIGHT == bytes([188])
    assert pc.QUADRANT_BOTTOM_LEFT == bytes([187])
    assert pc.QUADRANT_BOTTOM_RIGHT == bytes([172])
    assert pc.QUADRANT_BOTTOM_RIGHT_255_VARIANT == bytes([236])
    assert pc.QUADRANT_DIAGONAL_TL_BR == bytes([191])


def test_dither_blocks():
    assert pc.DITHER_BLOCK_126 == bytes([126])
    assert pc.DITHER_BLOCK_166 == bytes([166])
    assert pc.DITHER_BLOCK_222 == bytes([222])
    assert pc.DITHER_BLOCK_230 == bytes([230])
    assert pc.DITHER_BLOCK_255 == bytes([255])
    assert pc.LEFT_HALF_DITHER == bytes([124])
    assert pc.LEFT_HALF_DITHER_220 == bytes([220])
    assert pc.BOTTOM_HALF_DITHER == bytes([168])
    assert pc.BOTTOM_HALF_DITHER_BR_COLORED == bytes([232])


def test_bars_and_thin_lines():
    assert pc.THIN_BAR_TOP == bytes([163])
    assert pc.THIN_BAR_BOTTOM == bytes([164])
    assert pc.QUARTER_BAR_LEFT == bytes([165])
    assert pc.QUARTER_BAR_RIGHT == bytes([170])
    assert pc.QUARTER_BAR_BOTTOM == bytes([175])
    assert pc.QUARTER_BAR_TOP == bytes([183])
    assert pc.THIN_BAR_LEFT == bytes([180])
    assert pc.BAR_LEFT_2PX == bytes([181])
    assert pc.BAR_RIGHT_2PX == bytes([182])
    assert pc.BAR_TOP_2PX == bytes([184])
    assert pc.BAR_BOTTOM_2PX == bytes([185])
    assert pc.THIN_LINE_NEAR_BOTTOM == bytes([192])
    assert pc.THIN_LINE_CENTER_VERTICAL == bytes([221])
    assert pc.LINE_LEFT_2PX == bytes([244])
    assert pc.LINE_LEFT_3PX == bytes([245])
    assert pc.LINE_RIGHT_3PX == bytes([246])
    assert pc.LINE_TOP_1PX == bytes([247])
    assert pc.LINE_TOP_2PX == bytes([248])
    assert pc.LINE_BOTTOM_2PX == bytes([249])
    assert pc.THIN_BAR_BOTTOM_239 == bytes([239])


def test_half_bars_and_diagonals_and_misc():
    assert pc.LEFT_HALF_BAR == bytes([225])
    assert pc.BOTTOM_HALF_BAR == bytes([226])
    assert pc.DIAGONAL_BARS_CLEAR_LR == bytes([127])
    assert pc.DIAGONAL_BARS_CLEAR_RL == bytes([169])
    assert pc.DIAGONAL_BARS_FILLED_TL_BR == bytes([223])
    assert pc.DIAGONAL_BARS_FILLED_TR_BL == bytes([233])
    assert pc.PLUS_FULL_SIZE == bytes([123])
    assert pc.HORIZONTAL_LINE_FULL == bytes([96])


def test_no_two_confirmed_constants_share_a_byte_value():
    """Every named single-byte constant in petscii_codes.py must map to a
    distinct byte -- a collision here would mean two different real,
    hand-verified glyphs got assigned the same number by mistake."""
    seen = {}
    for name in dir(pc):
        if name.startswith("_"):
            continue
        value = getattr(pc, name)
        if isinstance(value, bytes) and len(value) == 1:
            n = value[0]
            assert n not in seen, f"{name} and {seen.get(n)} both map to byte {n}"
            seen[n] = name
