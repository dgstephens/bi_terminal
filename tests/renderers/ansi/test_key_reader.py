"""The 11 verification cases from the plan that produced this file, ported
into real tests — proves KeyReader's select-timeout-peek + one-byte
pushback design against a plain os.pipe(), deliberately the same code path
a real Standard I/O door process uses (its stdin is a pipe/socket, not a
local tty)."""

import os
import time

from bi_terminal.renderers.ansi.io import KeyReader


def _keys(write_bytes: bytes, count: int):
    r_fd, w_fd = os.pipe()
    try:
        os.write(w_fd, write_bytes)
        reader = KeyReader(r_fd)
        return [reader.read_key(timeout=1.0) for _ in range(count)]
    finally:
        os.close(r_fd)
        os.close(w_fd)


def test_plain_char():
    assert _keys(b"b", 1) == ["b"]


def test_enter_cr():
    assert _keys(b"\r", 1) == ["enter"]


def test_enter_lf():
    assert _keys(b"\n", 1) == ["enter"]


def test_arrow_up():
    assert _keys(b"\x1b[A", 1) == ["up"]


def test_arrow_down():
    assert _keys(b"\x1b[B", 1) == ["down"]


def test_arrow_left():
    assert _keys(b"\x1b[D", 1) == ["left"]


def test_arrow_right():
    assert _keys(b"\x1b[C", 1) == ["right"]


def test_lone_escape():
    assert _keys(b"\x1b", 1) == ["escape"]


def test_backspace_del():
    assert _keys(b"\x7f", 1) == ["backspace"]


def test_backspace_bs():
    assert _keys(b"\x08", 1) == ["backspace"]


def test_tab():
    assert _keys(b"\t", 1) == ["tab"]


def test_ctrl_c():
    assert _keys(b"\x03", 1) == ["ctrl+c"]


def test_two_plain_chars_queued():
    assert _keys(b"hi", 2) == ["h", "i"]


def test_escape_then_unrelated_char_is_not_swallowed():
    """The exact bug the first prototype had: peeking past ESC for '[' and
    discarding the byte when it wasn't '[' silently ate the next keypress."""
    assert _keys(b"\x1bx", 2) == ["escape", "x"]


def test_escape_then_a_real_arrow_key_as_a_separate_keystroke():
    assert _keys(b"\x1b\x1b[A", 2) == ["escape", "up"]


def test_rapid_sequence_chars_then_arrow_then_enter():
    assert _keys(b"ab\x1b[A\r", 4) == ["a", "b", "up", "enter"]


def test_timeout_returns_none_without_hanging():
    r_fd, w_fd = os.pipe()
    try:
        reader = KeyReader(r_fd)
        t0 = time.monotonic()
        result = reader.read_key(timeout=0.05)
        elapsed = time.monotonic() - t0
        assert result is None
        assert elapsed < 0.5
    finally:
        os.close(r_fd)
        os.close(w_fd)


def test_lone_escape_resolves_quickly_not_after_full_read_timeout():
    r_fd, w_fd = os.pipe()
    try:
        os.write(w_fd, b"\x1b")
        reader = KeyReader(r_fd)
        t0 = time.monotonic()
        result = reader.read_key(timeout=5.0)
        elapsed = time.monotonic() - t0
        assert result == "escape"
        assert elapsed < 0.5  # resolved via the 50ms peek, not the 5s read timeout
    finally:
        os.close(r_fd)
        os.close(w_fd)


def test_eof_on_closed_write_end():
    r_fd, w_fd = os.pipe()
    os.close(w_fd)  # nothing will ever be written
    try:
        reader = KeyReader(r_fd)
        assert reader.read_key(timeout=0.5) is None
    finally:
        os.close(r_fd)
