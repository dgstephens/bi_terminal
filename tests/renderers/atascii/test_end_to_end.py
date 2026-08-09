"""True end-to-end tests: real AtasciiRenderer + real AppDriver + a mocked
API client, driven by scripted input bytes over real pipes."""

import io as pyio
import os
from unittest.mock import MagicMock, patch

from bi_terminal.core import config as config_module
from bi_terminal.driver import AppDriver
from bi_terminal.renderers.atascii import atascii_codes as ac
from bi_terminal.renderers.atascii.io import AtasciiIO
from bi_terminal.renderers.atascii.renderer import AtasciiRenderer

RET = ac.RETURN


def _run(write_bytes: bytes, cfg: dict, client):
    r_fd, w_fd = os.pipe()
    os.write(w_fd, write_bytes)
    out = pyio.BytesIO()
    io_obj = AtasciiIO(r_fd, out)
    renderer = AtasciiRenderer(io_obj)
    exits = []
    driver = AppDriver(cfg, client, renderer, on_exit=lambda: exits.append(True))
    with patch.object(config_module, "save"):
        driver.run()
    os.close(r_fd)
    os.close(w_fd)
    return out.getvalue(), exits


def _cfg():
    return {
        "base_url": "https://example.invalid/api",
        "token": "t",
        "userId": "u1",
        "email": "daniel@example.com",
        "image_mode": "none",
    }


def test_view_bins_then_back_then_exit():
    client = MagicMock()
    client.get_item_count.return_value = {"number": 1}
    client.get_bins_by_user.return_value = {
        "bins": [{"id": "b1", "binName": "Shelf A", "items": []}]
    }
    val, exits = _run(b"b" + ac.ESCAPE + b"x", _cfg(), client)
    assert exits == [True]
    assert b"Bin Inventory" in val
    assert b"My Bins" in val
    # "Shelf A" is the only/default-highlighted list row, so its bytes are
    # inverse-video-encoded (high bit set) -- the PLAIN bytes genuinely
    # don't appear, only the inverted form does. Confirmed correct behavior
    # by hand-computing the expected inverted bytes before writing this
    # assertion, not assumed.
    assert ac.inverse(b"Shelf A") in val
    client.get_bins_by_user.assert_called_once_with("u1")


def test_create_bin_end_to_end():
    client = MagicMock()
    client.get_item_count.return_value = {"number": 0}
    client.create_bin.return_value = {"bin": {"id": "b1", "binName": "New Shelf"}}
    val, exits = _run(b"w" + b"New Shelf" + RET + RET * 6 + b"x", _cfg(), client)
    assert exits == [True]
    client.create_bin.assert_called_once()
    assert client.create_bin.call_args.kwargs["bin_name"] == "New Shelf"
    assert b"created" in val.lower()


def test_search_no_results_then_exit():
    client = MagicMock()
    client.get_item_count.return_value = {"number": 0}
    client.search_items.return_value = {"items": []}
    val, exits = _run(b"s" + b"nothing" + RET + ac.ESCAPE + b"x", _cfg(), client)
    assert exits == [True]
    assert b"no results" in val.lower()
    client.search_items.assert_called_once_with("nothing")


def test_output_never_contains_raw_utf8_em_dash():
    """ATASCII legitimately uses the full 0-255 byte range (inverse video
    sets the high bit on otherwise-normal text), so unlike the PETSCII
    equivalent test there's no meaningful "known control bytes" allowlist
    to check here — the real regression coverage is that the em dash never
    leaks through as a 2-byte UTF-8 sequence."""
    client = MagicMock()
    client.get_item_count.return_value = {"number": 0}
    client.get_bins_by_user.return_value = {"bins": []}
    val, exits = _run(b"b" + ac.ESCAPE + b"x", _cfg(), client)
    assert exits == [True]
    assert "—".encode("utf-8") not in val
