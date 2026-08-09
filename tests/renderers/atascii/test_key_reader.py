"""AtasciiKeyReader tests — pipe-based, no tty dependency. Same shape as
PETSCII's equivalent test file (raw ATASCII, like raw PETSCII, has no
multi-byte escape sequences to disambiguate)."""

import os
import time

from bi_terminal.renderers.atascii.io import AtasciiKeyReader


def _keys(write_bytes: bytes, count: int):
    r_fd, w_fd = os.pipe()
    try:
        os.write(w_fd, write_bytes)
        reader = AtasciiKeyReader(r_fd)
        return [reader.read_key(timeout=1.0) for _ in range(count)]
    finally:
        os.close(r_fd)
        os.close(w_fd)


def test_plain_char():
    assert _keys(bytes([98]), 1) == ["b"]


def test_return_155_is_enter():
    assert _keys(bytes([155]), 1) == ["enter"]


def test_cursor_up_28():
    assert _keys(bytes([28]), 1) == ["up"]


def test_cursor_down_29():
    assert _keys(bytes([29]), 1) == ["down"]


def test_cursor_left_30():
    assert _keys(bytes([30]), 1) == ["left"]


def test_cursor_right_31():
    assert _keys(bytes([31]), 1) == ["right"]


def test_delete_126_is_backspace():
    assert _keys(bytes([126]), 1) == ["backspace"]


def test_escape_27():
    assert _keys(bytes([27]), 1) == ["escape"]


def test_tab_127():
    assert _keys(bytes([127]), 1) == ["tab"]


def test_ctrl_c():
    assert _keys(bytes([3]), 1) == ["ctrl+c"]


def test_two_plain_chars_queued():
    assert _keys(b"hi", 2) == ["h", "i"]


def test_digits_and_punctuation_pass_through():
    assert _keys(bytes([ord("5")]), 1) == ["5"]
    assert _keys(bytes([ord("-")]), 1) == ["-"]


def test_no_disambiguation_needed_resolves_essentially_instantly():
    r_fd, w_fd = os.pipe()
    try:
        os.write(w_fd, bytes([28]))
        reader = AtasciiKeyReader(r_fd)
        t0 = time.monotonic()
        result = reader.read_key(timeout=5.0)
        elapsed = time.monotonic() - t0
        assert result == "up"
        assert elapsed < 0.1
    finally:
        os.close(r_fd)
        os.close(w_fd)


def test_timeout_returns_none_without_hanging():
    r_fd, w_fd = os.pipe()
    try:
        reader = AtasciiKeyReader(r_fd)
        t0 = time.monotonic()
        result = reader.read_key(timeout=0.05)
        elapsed = time.monotonic() - t0
        assert result is None
        assert elapsed < 0.5
    finally:
        os.close(r_fd)
        os.close(w_fd)


def test_eof_on_closed_write_end():
    r_fd, w_fd = os.pipe()
    os.close(w_fd)
    try:
        reader = AtasciiKeyReader(r_fd)
        assert reader.read_key(timeout=0.5) is None
    finally:
        os.close(r_fd)


def test_unrecognized_control_byte_is_ignored_not_crashed():
    """A byte >=128 this reader doesn't map (e.g. an inverse-video
    character arriving as bogus input) must be silently ignored, not raise
    -- followed by a real key to confirm the reader keeps working."""
    assert _keys(bytes([200]) + b"b", 2) == [None, "b"]


def test_return_is_155_not_ascii_13():
    """The exact confirmed-real difference from PETSCII (whose RETURN
    genuinely is 13) -- plain ASCII CR must NOT be treated as enter here."""
    assert _keys(bytes([13]), 1) != ["enter"]
