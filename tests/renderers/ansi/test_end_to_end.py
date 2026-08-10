"""True end-to-end tests: real AnsiRenderer + real AppDriver + a mocked API
client, driven by scripted input bytes over real pipes — proves the ANSI
renderer actually works with the shared driver, not just in isolation."""

import io as pyio
import os
from unittest.mock import MagicMock, patch

from bi_terminal.core import config as config_module
from bi_terminal.driver import AppDriver
from bi_terminal.renderers.ansi.io import AnsiIO
from bi_terminal.renderers.ansi.renderer import AnsiRenderer


def _run(write_bytes: bytes, cfg: dict, client):
    r_fd, w_fd = os.pipe()
    os.write(w_fd, write_bytes)
    out = pyio.StringIO()
    io_obj = AnsiIO(r_fd, out)
    renderer = AnsiRenderer(io_obj)
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
    # This test drives AppDriver directly (see _run() above), not AnsiApp —
    # "Goodbye!" is AnsiApp's own on_exit hook body (renderers/ansi/app.py),
    # not something AppDriver writes itself, so it's deliberately not
    # asserted here (test_view_bins_then_back_then_exit intentionally tests
    # the driver+renderer combination, not the full app wiring).
    text, exits = _run(b"b\x1bx", _cfg(), client)
    assert exits == [True]
    assert "Bin Inventory" in text
    assert "My Bins" in text
    assert "Shelf A" in text
    client.get_bins_by_user.assert_called_once_with("u1")


def test_open_bin_detail_and_back_out():
    client = MagicMock()
    client.get_item_count.return_value = {"number": 0}
    client.get_bins_by_user.return_value = {
        "bins": [{"id": "b1", "binName": "Shelf A", "items": [], "description": "Art supplies"}]
    }
    # 'b' My Bins -> Enter (open the only bin) -> 'b' Back (bin_detail's
    # shortcut, per specs/menus.py) -> Esc (My Bins) -> 'x' Exit
    text, exits = _run(b"b\rb\x1bx", _cfg(), client)
    assert exits == [True]
    assert "Shelf A" in text
    assert "Art supplies" in text


def test_create_bin_end_to_end():
    client = MagicMock()
    client.get_item_count.return_value = {"number": 0}
    client.create_bin.return_value = {"bin": {"id": "b1", "binName": "New Shelf"}}
    # 'w' New Bin -> type "New Shelf" for bin_name, Enter -> Enter through
    # every remaining field (description, location, bin_type, public,
    # sw_emails, image_path = 6 fields, all blank/default) -> back at main
    # -> 'x' Exit
    text, exits = _run(b"w" + b"New Shelf\r" + b"\r" * 6 + b"x", _cfg(), client)
    assert exits == [True]
    client.create_bin.assert_called_once()
    assert client.create_bin.call_args.kwargs["bin_name"] == "New Shelf"
    assert "created" in text.lower()


def test_search_no_results_then_exit():
    client = MagicMock()
    client.get_item_count.return_value = {"number": 0}
    client.search_items.return_value = {"items": []}
    # 's' Search -> type "nothing" for query -> Enter -> notify "No results" ->
    # search form shown again -> Esc -> main -> 'x' Exit
    text, exits = _run(b"s" + b"nothing\r" + b"\x1bx", _cfg(), client)
    assert exits == [True]
    assert "no results" in text.lower()
    client.search_items.assert_called_once_with("nothing")


def test_output_never_contains_raw_utf8_em_dash():
    """Real bug, fixed 2026-08-10: the main menu title itself
    ("Bin Inventory — N items", specs/menus.py) contains a genuine em dash
    -- AnsiIO had zero sanitization, so every single real session sent this
    over the wire as 3 raw UTF-8 bytes a CP437 BBS terminal can't read.
    Mirrors PETSCII/ATASCII's identical end-to-end regression test."""
    client = MagicMock()
    client.get_item_count.return_value = {"number": 5}
    text, exits = _run(b"x", _cfg(), client)
    assert exits == [True]
    assert "—" not in text
    assert "Bin Inventory" in text
