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
"""

from unittest.mock import MagicMock, patch

from bi_terminal.renderers.petscii import petscii_codes as pc
from bi_terminal.renderers.petscii.petscii_art import (
    GRID_WIDTH,
    _nearest_color,
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
    # Not wrapped in REVERSE_ON/OFF here -- that's the caller's job now
    # (a display/pacing concern, not conversion), see renderer.py.
    assert not any(row.startswith(pc.REVERSE_ON) for row in rows)


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


# ── Tiered detail mode (2026-08-12) ─────────────────────────────────────
# Added after Daniel -- who's built exactly this technique before, on a
# monochrome 6502 computer he designed himself -- asked whether PETSCII's
# graphic characters could add detail beyond one flat color per cell.
# Samples each cell at 2x horizontal resolution and picks one of three
# tiers based on how different the two sub-pixels are. LEFT_HALF_BLOCK/
# RIGHT_HALF_BLOCK/MEDIUM_SHADE's exact byte values are explicitly NOT
# independently verified yet (see petscii_codes.py's own caveat) -- these
# tests cover the SELECTION LOGIC (which tier gets picked, and that the
# result is well-formed), not whether the specific glyphs are visually
# correct on a real screen, which is pending Daniel's own live look.


def _split_image(width_cells, height, left_color, right_color):
    """A fake image where every cell's left half is one color and right
    half is another -- lets a test control the two sub-pixels a specific
    cell will see without needing a real image."""
    img = MagicMock()
    img.height = height
    img.width = width_cells  # only used for the aspect-ratio calc
    img.convert.return_value = img
    img.resize.return_value = img

    def _getpixel(xy):
        x, _y = xy
        return left_color if x % 2 == 0 else right_color

    img.getpixel.side_effect = _getpixel
    return img


def test_identical_subpixels_render_as_plain_solid_block():
    """No visible change from the original v1 algorithm when there's
    nothing to add detail about -- a uniform region still just renders as
    a plain color fill, not a dithered or edged one."""
    mock_resp = MagicMock()
    mock_resp.content = b"fake-bytes"
    fake_img = _split_image(100, 100, (255, 0, 0), (255, 0, 0))  # same color both sides
    with patch("requests.get", return_value=mock_resp), patch("PIL.Image.open", return_value=fake_img):
        rows = image_to_petscii_rows("https://example.com/x.png")
    joined = b"".join(rows)
    assert pc.MEDIUM_SHADE not in joined
    assert pc.RIGHT_HALF_BLOCK not in joined


def test_slightly_different_subpixels_use_medium_shade():
    mock_resp = MagicMock()
    mock_resp.content = b"fake-bytes"
    # Squared distance = 60**2 = 3600 -- between _DITHER_THRESHOLD (2000)
    # and _EDGE_THRESHOLD (8000).
    fake_img = _split_image(100, 100, (100, 100, 100), (160, 100, 100))
    with patch("requests.get", return_value=mock_resp), patch("PIL.Image.open", return_value=fake_img):
        rows = image_to_petscii_rows("https://example.com/x.png")
    joined = b"".join(rows)
    assert pc.MEDIUM_SHADE in joined
    assert pc.RIGHT_HALF_BLOCK not in joined


def test_very_different_subpixels_use_right_half_block():
    mock_resp = MagicMock()
    mock_resp.content = b"fake-bytes"
    fake_img = _split_image(100, 100, (0, 0, 0), (255, 255, 255))  # black vs white -- a real edge
    with patch("requests.get", return_value=mock_resp), patch("PIL.Image.open", return_value=fake_img):
        rows = image_to_petscii_rows("https://example.com/x.png")
    joined = b"".join(rows)
    assert pc.RIGHT_HALF_BLOCK in joined
    assert pc.MEDIUM_SHADE not in joined


def test_rgb_distance_is_symmetric_and_zero_for_identical_colors():
    from bi_terminal.renderers.petscii.petscii_art import _rgb_distance

    assert _rgb_distance((10, 20, 30), (10, 20, 30)) == 0
    assert _rgb_distance((0, 0, 0), (255, 255, 255)) == _rgb_distance((255, 255, 255), (0, 0, 0))
    assert _rgb_distance((0, 0, 0), (255, 255, 255)) > 0
