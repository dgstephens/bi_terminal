"""True end-to-end tests: real PetsciiRenderer + real AppDriver + a mocked
API client, driven by scripted input bytes over real pipes."""

import io as pyio
import os
from unittest.mock import MagicMock, patch

from bi_terminal.core import config as config_module
from bi_terminal.driver import AppDriver
from bi_terminal.renderers.petscii import petscii_codes as pc
from bi_terminal.renderers.petscii.io import PetsciiIO
from bi_terminal.renderers.petscii.renderer import PetsciiRenderer

RET = pc.RETURN


def _run(write_bytes: bytes, cfg: dict, client):
    r_fd, w_fd = os.pipe()
    os.write(w_fd, write_bytes)
    out = pyio.BytesIO()
    io_obj = PetsciiIO(r_fd, out)
    renderer = PetsciiRenderer(io_obj)
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
    val, exits = _run(b"b" + bytes([0x1B]) + b"x", _cfg(), client)
    assert exits == [True]
    assert b"Bin Inventory" in val
    assert b"My Bins" in val
    assert b"Shelf A" in val
    client.get_bins_by_user.assert_called_once_with("u1")


def test_create_bin_end_to_end():
    client = MagicMock()
    client.get_item_count.return_value = {"number": 0}
    client.create_bin.return_value = {"bin": {"id": "b1", "binName": "New Shelf"}}
    # 'w' New Bin -> type "New Shelf" for bin_name, Enter -> Enter through
    # description, location, bin_type, public, sw_emails, image_path (6
    # more fields) -> back at main -> 'x' Exit
    val, exits = _run(b"w" + b"New Shelf" + RET + RET * 6 + b"x", _cfg(), client)
    assert exits == [True]
    client.create_bin.assert_called_once()
    assert client.create_bin.call_args.kwargs["bin_name"] == "New Shelf"
    assert b"created" in val.lower()


def test_search_no_results_then_exit():
    client = MagicMock()
    client.get_item_count.return_value = {"number": 0}
    client.search_items.return_value = {"items": []}
    val, exits = _run(b"s" + b"nothing" + RET + bytes([0x1B]) + b"x", _cfg(), client)
    assert exits == [True]
    assert b"no results" in val.lower()
    client.search_items.assert_called_once_with("nothing")


def test_output_never_contains_raw_utf8_em_dash():
    """A blanket regression check across a real multi-screen flow: no
    em-dash (or any non-ASCII byte sequence) should ever reach the wire."""
    client = MagicMock()
    client.get_item_count.return_value = {"number": 0}
    client.get_bins_by_user.return_value = {"bins": []}
    val, exits = _run(b"b" + bytes([0x1B]) + b"x", _cfg(), client)
    assert exits == [True]
    assert "—".encode("utf-8") not in val
    # every byte is either a known PETSCII control byte or valid ASCII
    for byte in val:
        assert byte < 128 or byte in {
            v[0]
            for v in vars(pc).values()
            if isinstance(v, bytes) and len(v) == 1
        }
