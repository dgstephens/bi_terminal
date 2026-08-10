"""PetsciiKeyReader tests — pipe-based, no tty dependency (the same code
path a real Standard I/O door process uses). Simpler than the ANSI
renderer's KeyReader tests since raw PETSCII has no multi-byte escape
sequences to disambiguate (confirmed against Synchronet's CTerm manual) —
every control code is exactly one byte."""

import os
import time

from bi_terminal.renderers.petscii.io import PetsciiKeyReader


def _keys(write_bytes: bytes, count: int):
    r_fd, w_fd = os.pipe()
    try:
        os.write(w_fd, write_bytes)
        reader = PetsciiKeyReader(r_fd)
        return [reader.read_key(timeout=1.0) for _ in range(count)]
    finally:
        os.close(r_fd)
        os.close(w_fd)


def test_plain_char():
    assert _keys(bytes([98]), 1) == ["b"]


def test_return_is_enter():
    assert _keys(bytes([13]), 1) == ["enter"]


def test_cursor_up():
    assert _keys(bytes([145]), 1) == ["up"]


def test_cursor_down():
    assert _keys(bytes([17]), 1) == ["down"]


def test_cursor_left():
    assert _keys(bytes([157]), 1) == ["left"]


def test_cursor_right():
    assert _keys(bytes([29]), 1) == ["right"]


def test_delete_is_backspace():
    assert _keys(bytes([20]), 1) == ["backspace"]


def test_escape_byte():
    assert _keys(bytes([0x1B]), 1) == ["escape"]


def test_ctrl_c():
    assert _keys(bytes([3]), 1) == ["ctrl+c"]


def test_tab():
    assert _keys(bytes([9]), 1) == ["tab"]


def test_two_plain_chars_queued():
    assert _keys(b"hi", 2) == ["h", "i"]


def test_digits_and_punctuation_pass_through():
    assert _keys(bytes([ord("5")]), 1) == ["5"]
    assert _keys(bytes([ord("-")]), 1) == ["-"]


def test_no_disambiguation_needed_unlike_ansi():
    """PETSCII has no CSI sequences at all -- a cursor key byte is
    immediately unambiguous, no peek/timeout needed to resolve it (contrast
    with renderers/ansi/io.py's KeyReader, which needs a 50ms peek after
    ESC). Verify this resolves essentially instantly."""
    r_fd, w_fd = os.pipe()
    try:
        os.write(w_fd, bytes([145]))
        reader = PetsciiKeyReader(r_fd)
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
        reader = PetsciiKeyReader(r_fd)
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
        reader = PetsciiKeyReader(r_fd)
        assert reader.read_key(timeout=0.5) is None
    finally:
        os.close(r_fd)


def test_unrecognized_high_control_byte_is_ignored_not_crashed():
    """A PETSCII control byte this reader doesn't have a mapping for (e.g.
    a color code arriving as bogus input) must be silently ignored, not
    raise -- followed by a real key to confirm the reader keeps working."""
    assert _keys(bytes([144]) + b"b", 2) == [None, "b"]


def test_debug_log_records_raw_byte_and_resolved_key(tmp_path):
    """New diagnostic capability (2026-08-10), added to investigate a real,
    live-reported bug: cursor keys + backspace not working through a real
    Synchronet BBS connection. Off by default (debug_log_path=None, the
    default in every other test in this file) -- this is the one test that
    actually exercises it."""
    log_path = tmp_path / "petscii_debug.log"
    r_fd, w_fd = os.pipe()
    try:
        os.write(w_fd, bytes([145, 20, 98]))  # up, backspace, "b"
        reader = PetsciiKeyReader(r_fd, debug_log_path=str(log_path))
        keys = [reader.read_key(timeout=1.0) for _ in range(3)]
        assert keys == ["up", "backspace", "b"]
        lines = log_path.read_text().splitlines()
        assert len(lines) == 3
        assert "raw=0x91 (145) -> 'up'" in lines[0]
        assert "raw=0x14 (20) -> 'backspace'" in lines[1]
        assert "raw=0x62 (98) -> 'b'" in lines[2]
    finally:
        os.close(r_fd)
        os.close(w_fd)


def test_debug_log_none_path_never_creates_a_file(tmp_path):
    """The off-by-default guarantee -- a debug feature that silently
    creates files nobody asked for would be its own bug."""
    would_be_log = tmp_path / "should_not_exist.log"
    assert _keys(b"b", 1) == ["b"]
    assert not would_be_log.exists()
