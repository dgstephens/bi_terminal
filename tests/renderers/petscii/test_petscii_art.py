"""Unit tests for petscii_art.py -- the PIL -> PETSCII color-block image
converter. Real image support, built 2026-08-11 -- see the module's own
docstring for the protocol constraints (no per-character background color
in real PETSCII, fixed 16-color hardware palette) that shape the approach.

image_to_petscii_rows() returns a List[bytes] (one chunk per row), not one
concatenated blob -- changed 2026-08-12 in response to a real live report
(an image showed only its first row through a real Synchronet connection)
so the caller can write+flush+pace each row individually. See
renderer.py's show_image() and io.py's PetsciiIO.write_rows_paced() for
the write-side half of that fix.

Quadrant-glyph mode (2026-08-13): each cell now samples a 2x2 sub-pixel
grid and picks a glyph from petscii_codes.py's CONFIRMED byte values (real
data Daniel read off a real SyncTERM screen, not guesses) -- see the
module's own docstring for the full on/off/glyph-selection rules. Rows are
now self-contained regarding REVERSE_ON/OFF (a contract change from the
earlier flat mosaic, where the caller wrapped the whole row externally).
"""

from unittest.mock import MagicMock, patch

from bi_terminal.renderers.petscii import petscii_codes as pc
from bi_terminal.renderers.petscii.petscii_art import (
    GRID_WIDTH,
    _average_color,
    _has_significant_color_variance,
    _nearest_color,
    _quadrant_cell,
    image_to_petscii_rows,
)


def test_nearest_color_exact_matches():
    """Every one of Pepto's 16 measured VIC-II RGB values must map back to
    its own control byte exactly -- the whole point of the palette table."""
    assert _nearest_color((0x00, 0x00, 0x00)) == pc.BLACK
    assert _nearest_color((0xFF, 0xFF, 0xFF)) == pc.WHITE
    assert _nearest_color((0x68, 0x37, 0x2B)) == pc.RED
    assert _nearest_color((0x35, 0x28, 0x79)) == pc.BLUE


def test_nearest_color_picks_closest_not_first():
    """A color that's clearly closer to red than to anything else must
    resolve to red, even though red isn't first in the palette table."""
    assert _nearest_color((0x70, 0x30, 0x25)) == pc.RED  # near-exact red, slightly off
    assert _nearest_color((0x10, 0x10, 0x10)) == pc.BLACK  # near-black


def _fake_image(width=4, height=4, color=(255, 0, 0)):
    img = MagicMock()
    img.height = height
    img.width = width
    img.convert.return_value = img
    img.resize.return_value = img
    img.getpixel.return_value = color
    return img


def test_image_to_petscii_rows_returns_none_on_missing_url():
    assert image_to_petscii_rows("") is None
    assert image_to_petscii_rows(None) is None


def test_image_to_petscii_rows_returns_none_on_network_failure():
    """requests/PIL are imported LOCALLY inside the function (matching
    _shared_ansi_art.py's style, which this module deliberately mirrors),
    so the real library attributes are what needs patching -- not
    petscii_art.requests, which doesn't exist as a module-level name."""
    with patch("requests.get", side_effect=Exception("connection refused")):
        assert image_to_petscii_rows("https://example.com/x.png") is None


def test_image_to_petscii_rows_returns_none_on_bad_image_data():
    """A URL that resolves but isn't actually image data (PIL raises on
    open) -- must fail gracefully, not crash the caller."""
    mock_resp = MagicMock()
    mock_resp.content = b"not an image"
    with patch("requests.get", return_value=mock_resp), patch(
        "PIL.Image.open", side_effect=Exception("cannot identify image file")
    ):
        assert image_to_petscii_rows("https://example.com/x.png") is None


def test_image_to_petscii_rows_returns_one_chunk_per_row_ending_in_return():
    """Real regression test for the live-reported bug this shape change
    fixes: every row must be its own list entry, each ending in RETURN, so
    the caller can write/flush/pace them individually instead of one big
    burst write.

    Note: the fake image's own width/height only control the ASPECT RATIO
    fed into the row-count formula (h = GRID_WIDTH * aspect * 0.5) -- the
    actual grid is always GRID_WIDTH columns wide, real image dimensions
    never map 1:1 to row count. A square (1:1) source image works out to
    19 rows here; the exact number isn't the point, "more than one row
    from a normal (non-panoramic) image" is."""
    mock_resp = MagicMock()
    mock_resp.content = b"fake-bytes"
    fake_img = _fake_image(width=100, height=100, color=(0, 0, 0))  # square -> aspect 1.0
    with patch("requests.get", return_value=mock_resp), patch("PIL.Image.open", return_value=fake_img):
        rows = image_to_petscii_rows("https://example.com/x.png")
    assert rows is not None
    assert len(rows) > 1
    for row in rows:
        assert row.endswith(pc.RETURN)
    # This particular fake image is solid BLACK -- every sub-pixel
    # quantizes to "off," so no glyph in this specific case needs
    # REVERSE_ON at all. See test_solid_nonblack_image_embeds_reverse_
    # toggling_per_row below for the contract-change case that does.


def test_image_to_petscii_rows_only_emits_color_byte_on_change_within_a_row():
    """A run-length-style optimization, not just correctness: a solid-color
    image should emit the color control byte ONCE across the WHOLE image,
    not once per cell -- real politeness for a 40-column screen and a real
    (if slow) network link, not just aesthetics."""
    mock_resp = MagicMock()
    mock_resp.content = b"fake-bytes"
    fake_img = _fake_image(width=100, height=100, color=(0xFF, 0xFF, 0xFF))  # -> pure white
    with patch("requests.get", return_value=mock_resp), patch("PIL.Image.open", return_value=fake_img):
        rows = image_to_petscii_rows("https://example.com/x.png")
    assert sum(row.count(pc.WHITE) for row in rows) == 1


def test_image_to_petscii_rows_color_carries_across_rows():
    """The run-length optimization tracks color across row boundaries too
    -- a solid-color image across multiple rows should still only emit the
    color byte once, on the very first cell, not once per row."""
    mock_resp = MagicMock()
    mock_resp.content = b"fake-bytes"
    fake_img = _fake_image(width=2, height=3, color=(0xFF, 0xFF, 0xFF))
    with patch("requests.get", return_value=mock_resp), patch("PIL.Image.open", return_value=fake_img):
        rows = image_to_petscii_rows("https://example.com/x.png")
    total_color_bytes = sum(row.count(pc.WHITE) for row in rows)
    assert total_color_bytes == 1


def test_grid_width_fits_the_40_column_screen():
    assert GRID_WIDTH < 40


def test_solid_nonblack_image_embeds_reverse_toggling_per_row():
    """Contract change from the earlier flat mosaic (renderer.py used to
    wrap every row in REVERSE_ON/OFF externally) -- rows are now
    self-contained. A solid non-black image makes every cell an "all 4 on"
    solid block, so every row should both start reversed and end back in
    normal mode (the explicit REVERSE_OFF at each row's end, since
    current_reverse resets per row -- matching the confirmed Synchronet
    behavior of resetting reverse state at every RETURN, defensively,
    regardless of whether that's also true on other clients)."""
    mock_resp = MagicMock()
    mock_resp.content = b"fake-bytes"
    fake_img = _fake_image(width=10, height=10, color=(0xFF, 0xFF, 0xFF))
    with patch("requests.get", return_value=mock_resp), patch("PIL.Image.open", return_value=fake_img):
        rows = image_to_petscii_rows("https://example.com/x.png")
    assert rows
    for row in rows:
        assert pc.REVERSE_ON in row
        # every row must end back in normal mode, not left reversed
        assert row.index(pc.REVERSE_OFF) > row.index(pc.REVERSE_ON)
        assert row.endswith(pc.REVERSE_OFF + pc.RETURN)


# ── _quadrant_cell() ─────────────────────────────────────────────────────
# Direct tests of the on/off/glyph-selection rules -- see petscii_art.py's
# module docstring for the full reasoning. BLACK = "off," anything else =
# "on"; corners are (top_left, top_right, bottom_left, bottom_right).

_WHITE = (0xFF, 0xFF, 0xFF)
_BLACK = (0x00, 0x00, 0x00)


def test_quadrant_cell_all_off_is_plain_space():
    from bi_terminal.renderers.petscii.petscii_art import SPACE

    glyph, reverse, color = _quadrant_cell(_BLACK, _BLACK, _BLACK, _BLACK)
    assert glyph == SPACE
    assert reverse is False
    assert color is None


def test_quadrant_cell_all_on_is_reversed_solid_block():
    from bi_terminal.renderers.petscii.petscii_art import SPACE

    glyph, reverse, color = _quadrant_cell(_WHITE, _WHITE, _WHITE, _WHITE)
    assert glyph == SPACE
    assert reverse is True
    assert color == pc.WHITE


def test_quadrant_cell_single_corner_on_matches_confirmed_glyph():
    from bi_terminal.renderers.petscii.petscii_art import SPACE

    cases = [
        ((_WHITE, _BLACK, _BLACK, _BLACK), pc.QUADRANT_TOP_LEFT),
        ((_BLACK, _WHITE, _BLACK, _BLACK), pc.QUADRANT_TOP_RIGHT),
        ((_BLACK, _BLACK, _WHITE, _BLACK), pc.QUADRANT_BOTTOM_LEFT),
        ((_BLACK, _BLACK, _BLACK, _WHITE), pc.QUADRANT_BOTTOM_RIGHT),
    ]
    for corners, expected_glyph in cases:
        glyph, reverse, color = _quadrant_cell(*corners)
        assert glyph == expected_glyph
        assert glyph != SPACE
        assert reverse is False
        assert color == pc.WHITE


def test_quadrant_cell_confirmed_two_corner_combos():
    cases = [
        ((_WHITE, _BLACK, _WHITE, _BLACK), pc.LEFT_HALF_BLOCK),  # top-left + bottom-left
        ((_BLACK, _BLACK, _WHITE, _WHITE), pc.LOWER_HALF_BLOCK),  # bottom-left + bottom-right
        ((_WHITE, _BLACK, _BLACK, _WHITE), pc.QUADRANT_DIAGONAL_TL_BR),  # top-left + bottom-right
    ]
    for corners, expected_glyph in cases:
        glyph, reverse, color = _quadrant_cell(*corners)
        assert glyph == expected_glyph
        assert reverse is False
        assert color == pc.WHITE


def test_quadrant_cell_unconfirmed_two_corner_combos_round_up_to_solid_block():
    """Top half (TL+TR), right half (TR+BR), and the other diagonal
    (TR+BL) have no confirmed glyph in petscii_codes.py's CONFIRMED section
    -- Daniel's real character-browser survey of the full non-control byte
    range never found one, so these round up to a solid block rather than
    guess at an unconfirmed byte (see this module's docstring)."""
    from bi_terminal.renderers.petscii.petscii_art import SPACE

    cases = [
        (_WHITE, _WHITE, _BLACK, _BLACK),  # top half
        (_BLACK, _WHITE, _BLACK, _WHITE),  # right half
        (_BLACK, _WHITE, _WHITE, _BLACK),  # top-right + bottom-left diagonal
    ]
    for corners in cases:
        glyph, reverse, color = _quadrant_cell(*corners)
        assert glyph == SPACE
        assert reverse is True
        assert color == pc.WHITE


def test_quadrant_cell_three_corners_on_rounds_up_to_solid_block():
    """No confirmed 3-quadrant glyph exists either -- same fallback."""
    from bi_terminal.renderers.petscii.petscii_art import SPACE

    glyph, reverse, color = _quadrant_cell(_WHITE, _WHITE, _WHITE, _BLACK)
    assert glyph == SPACE
    assert reverse is True
    assert color == pc.WHITE


def test_quadrant_cell_mixed_colors_average_and_quantize():
    """When the "on" corners aren't identical, the cell's color is the
    average of just the ON corners (BLACK/off corners excluded from the
    average), quantized to the nearest palette entry -- not simply
    whichever corner happened to be sampled first."""
    red = (0x68, 0x37, 0x2B)  # exact palette RED
    glyph, reverse, color = _quadrant_cell(red, _BLACK, red, _BLACK)
    assert glyph == pc.LEFT_HALF_BLOCK
    assert color == pc.RED


def test_average_color_excludes_nothing_itself_caller_filters_off_pixels():
    """_average_color() itself just averages whatever list it's given --
    the "exclude off/BLACK corners" filtering happens in _quadrant_cell(),
    not here. Direct unit coverage of the averaging+quantization math."""
    assert _average_color([(0xFF, 0xFF, 0xFF), (0xFF, 0xFF, 0xFF)]) == pc.WHITE
    assert _average_color([(0x00, 0x00, 0x00)]) == pc.BLACK


# ── Dither glyphs for disagreeing "on" colors (2026-08-13) ────────────────
# Real, live-reported observation: "no dithered blocks" ever appeared, even
# though DITHER_BLOCK_* constants exist in petscii_codes.py -- they were
# transcribed from Daniel's notes but never wired into _quadrant_cell() at
# all until now. See petscii_art.py's module docstring for the full
# reasoning (color variance beats shape matching).

_RED = (0x68, 0x37, 0x2B)  # exact palette RED
_BLUE = (0x35, 0x28, 0x79)  # exact palette BLUE


def test_quadrant_cell_disagreeing_on_colors_use_dither_not_average():
    glyph, reverse, color = _quadrant_cell(_RED, _BLUE, _BLACK, _BLACK)
    assert glyph == pc.DITHER_BLOCK_166
    assert reverse is False
    assert color == _average_color([_RED, _BLUE])


def test_quadrant_cell_agreeing_on_colors_do_not_trigger_dither():
    """Sanity check for the other direction -- two "on" corners that ARE
    the same color must still use the normal shape match, not dither."""
    glyph, reverse, color = _quadrant_cell(_RED, _BLACK, _RED, _BLACK)
    assert glyph == pc.LEFT_HALF_BLOCK
    assert glyph != pc.DITHER_BLOCK_166


def test_quadrant_cell_single_on_pixel_never_triggers_dither():
    """A single "on" corner is trivially color-uniform (nothing to
    disagree with) -- must always use its confirmed corner glyph, never
    dither, regardless of which corner."""
    glyph, reverse, color = _quadrant_cell(_RED, _BLACK, _BLACK, _BLACK)
    assert glyph == pc.QUADRANT_TOP_LEFT
    assert glyph != pc.DITHER_BLOCK_166


def test_quadrant_cell_disagreeing_colors_override_confirmed_shape_match():
    """Color variance takes priority over shape matching, even when the
    on-pattern WOULD otherwise have an exact confirmed glyph (here,
    top-left + bottom-left would normally match LEFT_HALF_BLOCK) -- a
    shape glyph can only ever show ONE color, so picking one and silently
    discarding the disagreeing other would be worse than a texture that
    signals real mixed content."""
    glyph, reverse, color = _quadrant_cell(_RED, _BLACK, _BLUE, _BLACK)
    assert glyph == pc.DITHER_BLOCK_166


def test_quadrant_cell_all_four_on_disagreeing_colors_use_dither_not_solid():
    glyph, reverse, color = _quadrant_cell(_RED, _BLUE, _RED, _BLUE)
    assert glyph == pc.DITHER_BLOCK_166
    assert reverse is False
    assert color == _average_color([_RED, _BLUE, _RED, _BLUE])


# ── Dither over-triggering fix (2026-08-13) ───────────────────────────────
# Real, live-reported bug the SAME day dither first shipped: comparing
# QUANTIZED colors ("do these on-pixels round to two different palette
# entries at all") fired dither on ordinary photographic noise that
# happened to cross a palette-quantization boundary, not just genuine
# color transitions -- Daniel, looking at a real photo through the real
# door: "it's definitely got a lot of dithering going on. I think too
# much, really." Fixed by comparing actual RGB distance instead.


def test_has_significant_color_variance_close_colors_false():
    assert _has_significant_color_variance([(100, 100, 100), (105, 105, 105)]) is False


def test_has_significant_color_variance_far_colors_true():
    assert _has_significant_color_variance([(0, 0, 0), (255, 255, 255)]) is True


def test_has_significant_color_variance_single_pixel_is_trivially_false():
    assert _has_significant_color_variance([(255, 0, 0)]) is False


def test_quadrant_cell_close_colors_across_a_real_quantization_boundary_do_not_dither():
    """The direct regression test for the reported bug: two colors just
    1 unit per channel apart (squared distance 3 -- ordinary photographic
    noise) that happen to straddle a REAL quantization boundary (one
    quantizes to WHITE, the other to LIGHT_GREEN, confirmed empirically
    against the actual palette) must NOT trigger dither -- they're
    visually indistinguishable, not a real color transition."""
    from bi_terminal.renderers.petscii.petscii_art import SPACE

    near_white = (205, 205, 205)  # quantizes to WHITE
    near_light_green = (204, 204, 204)  # quantizes to LIGHT_GREEN -- 1 unit away
    assert _nearest_color(near_white) == pc.WHITE
    assert _nearest_color(near_light_green) == pc.LIGHT_GREEN

    glyph, reverse, color = _quadrant_cell(near_white, _BLACK, near_light_green, _BLACK)
    assert glyph != pc.DITHER_BLOCK_166
    assert glyph == pc.LEFT_HALF_BLOCK  # falls through to normal shape matching instead


def test_quadrant_cell_genuinely_different_colors_still_dither():
    """The other direction, still true after the fix -- a REAL color
    transition (not just noise near a boundary) must still trigger
    dither, same as before this fix."""
    glyph, reverse, color = _quadrant_cell(_RED, _BLACK, _BLUE, _BLACK)
    assert glyph == pc.DITHER_BLOCK_166
