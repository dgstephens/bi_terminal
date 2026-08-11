"""Unit tests for petscii_art.py -- the PIL -> PETSCII color-block image
converter. Real image support, built 2026-08-11 -- see the module's own
docstring for the protocol constraints (no per-character background color
in real PETSCII, fixed 16-color hardware palette) that shape the approach.
"""

from unittest.mock import MagicMock, patch

from bi_terminal.renderers.petscii import petscii_codes as pc
from bi_terminal.renderers.petscii.petscii_art import (
    GRID_WIDTH,
    _nearest_color,
    image_to_petscii_bytes,
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


def test_image_to_petscii_bytes_returns_none_on_missing_url():
    assert image_to_petscii_bytes("") is None
    assert image_to_petscii_bytes(None) is None


def test_image_to_petscii_bytes_returns_none_on_network_failure():
    """requests/PIL are imported LOCALLY inside the function (matching
    _shared_ansi_art.py's style, which this module deliberately mirrors),
    so the real library attributes are what needs patching -- not
    petscii_art.requests, which doesn't exist as a module-level name."""
    with patch("requests.get", side_effect=Exception("connection refused")):
        assert image_to_petscii_bytes("https://example.com/x.png") is None


def test_image_to_petscii_bytes_returns_none_on_bad_image_data():
    """A URL that resolves but isn't actually image data (PIL raises on
    open) -- must fail gracefully, not crash the caller."""
    mock_resp = MagicMock()
    mock_resp.content = b"not an image"
    with patch("requests.get", return_value=mock_resp), patch(
        "PIL.Image.open", side_effect=Exception("cannot identify image file")
    ):
        assert image_to_petscii_bytes("https://example.com/x.png") is None


def test_image_to_petscii_bytes_wraps_reverse_video_and_ends_with_reverse_off():
    """The core trick this whole approach depends on -- see the module
    docstring's protocol-constraint explanation: PETSCII has no per-cell
    background color at all, only REVERSE_ON turning a plain space into a
    solid block of the current foreground color. Every real render must
    start with REVERSE_ON and end with REVERSE_OFF, or a caller's screen
    would be left in reverse-video mode after viewing an image."""
    mock_resp = MagicMock()
    mock_resp.content = b"fake-bytes"
    fake_img = _fake_image(color=(0, 0, 0))  # solid black -> minimal, predictable output
    with patch("requests.get", return_value=mock_resp), patch("PIL.Image.open", return_value=fake_img):
        result = image_to_petscii_bytes("https://example.com/x.png")
    assert result is not None
    assert result.startswith(pc.REVERSE_ON)
    assert result.endswith(pc.REVERSE_OFF)


def test_image_to_petscii_bytes_only_emits_color_byte_on_change():
    """A run-length-style optimization, not just correctness: a solid-color
    image should emit the color control byte ONCE, not once per cell --
    real politeness for a 40-column screen and a real (if slow) network
    link, not just aesthetics."""
    mock_resp = MagicMock()
    mock_resp.content = b"fake-bytes"
    fake_img = _fake_image(width=1, height=1, color=(0xFF, 0xFF, 0xFF))  # -> pure white
    with patch("requests.get", return_value=mock_resp), patch("PIL.Image.open", return_value=fake_img):
        result = image_to_petscii_bytes("https://example.com/x.png")
    assert result.count(pc.WHITE) == 1


def test_grid_width_fits_the_40_column_screen():
    assert GRID_WIDTH < 40
