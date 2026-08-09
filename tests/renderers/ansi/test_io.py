import io as pyio
import os

from bi_terminal.renderers.ansi.io import AnsiIO, read_line
from bi_terminal.specs.base import CANCELLED


def _make(write_bytes: bytes):
    r_fd, w_fd = os.pipe()
    os.write(w_fd, write_bytes)
    out = pyio.StringIO()
    return AnsiIO(r_fd, out), out, (r_fd, w_fd)


def _close(fds):
    for fd in fds:
        try:
            os.close(fd)
        except OSError:
            pass


def test_write_translates_bare_newline_to_crlf():
    io_obj, out, fds = _make(b"")
    io_obj.write("line one\nline two\n")
    _close(fds)
    assert out.getvalue() == "line one\r\nline two\r\n"


def test_maybe_raw_mode_is_a_noop_on_a_non_tty_fd():
    """A pipe is never a tty — this is the same code path a real Standard
    I/O door's stdin takes (already-raw byte stream, no local tty to set
    raw), so it must not raise or block."""
    io_obj, out, fds = _make(b"")
    with io_obj.maybe_raw_mode():
        io_obj.write("inside\n")
    _close(fds)
    assert "inside" in out.getvalue()


def test_read_line_basic():
    io_obj, out, fds = _make(b"hello\r")
    result = read_line(io_obj)
    _close(fds)
    assert result == "hello"


def test_read_line_backspace_edits_correctly():
    io_obj, out, fds = _make(b"hi\x7fx\r")  # "hi", backspace, "x", enter -> "hx"
    result = read_line(io_obj)
    _close(fds)
    assert result == "hx"


def test_read_line_backspace_on_empty_buffer_is_a_noop():
    io_obj, out, fds = _make(b"\x7f\x7fok\r")
    result = read_line(io_obj)
    _close(fds)
    assert result == "ok"


def test_read_line_escape_returns_cancelled():
    io_obj, out, fds = _make(b"\x1b")
    result = read_line(io_obj)
    _close(fds)
    assert result is CANCELLED


def test_read_line_ctrl_c_also_returns_cancelled():
    io_obj, out, fds = _make(b"\x03")
    result = read_line(io_obj)
    _close(fds)
    assert result is CANCELLED


def test_read_line_password_mode_echoes_asterisks_not_the_characters():
    io_obj, out, fds = _make(b"secret\r")
    result = read_line(io_obj, password=True)
    _close(fds)
    assert result == "secret"
    assert "secret" not in out.getvalue()
    assert "*" * 6 in out.getvalue()


def test_read_line_initial_value_is_prefilled_and_editable():
    io_obj, out, fds = _make(b"\x7f\x7fZ\r")  # remove last 2 chars of "abc", add "Z" -> "aZ"
    result = read_line(io_obj, initial="abc")
    _close(fds)
    assert result == "aZ"


def test_read_line_ignores_arrow_keys_and_tab():
    io_obj, out, fds = _make(b"\x1b[A\x1b[B\tok\r")
    result = read_line(io_obj)
    _close(fds)
    assert result == "ok"
