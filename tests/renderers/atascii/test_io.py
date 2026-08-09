import io as pyio
import os

from bi_terminal.renderers.atascii import atascii_codes as ac
from bi_terminal.renderers.atascii.io import AtasciiIO, read_line
from bi_terminal.specs.base import CANCELLED


def _make(write_bytes: bytes):
    r_fd, w_fd = os.pipe()
    os.write(w_fd, write_bytes)
    out = pyio.BytesIO()
    return AtasciiIO(r_fd, out), out, (r_fd, w_fd)


def _close(fds):
    for fd in fds:
        try:
            os.close(fd)
        except OSError:
            pass


def test_write_raw_passes_bytes_through_unmodified():
    io_obj, out, fds = _make(b"")
    io_obj.write_raw(ac.CLR + ac.RETURN)
    _close(fds)
    assert out.getvalue() == ac.CLR + ac.RETURN


def test_write_text_sanitizes_em_dash():
    io_obj, out, fds = _make(b"")
    io_obj.write_text("Bin Inventory — 5 items")
    _close(fds)
    assert out.getvalue() == b"Bin Inventory - 5 items"


def test_write_text_never_double_encodes_high_bytes_as_utf8():
    io_obj, out, fds = _make(b"")
    io_obj.write_text("plain ascii text")
    _close(fds)
    assert len(out.getvalue()) == len("plain ascii text")


def test_write_text_replaces_truly_unknown_chars_with_question_mark():
    io_obj, out, fds = _make(b"")
    io_obj.write_text("emoji: \U0001f600")
    _close(fds)
    assert b"?" in out.getvalue()
    assert b"\xf0\x9f\x98\x80" not in out.getvalue()


def test_maybe_raw_mode_is_a_noop_on_a_non_tty_fd():
    io_obj, out, fds = _make(b"")
    with io_obj.maybe_raw_mode():
        io_obj.write_text("inside")
    _close(fds)
    assert out.getvalue() == b"inside"


def test_read_line_basic():
    io_obj, out, fds = _make(b"hello" + ac.RETURN)
    result = read_line(io_obj)
    _close(fds)
    assert result == "hello"


def test_read_line_backspace_uses_atascii_cursor_left_not_ascii_bs():
    io_obj, out, fds = _make(b"hi" + ac.DELETE + b"x" + ac.RETURN)
    result = read_line(io_obj)
    _close(fds)
    assert result == "hx"
    assert ac.CURSOR_LEFT + b" " + ac.CURSOR_LEFT in out.getvalue()
    assert b"\x08" not in out.getvalue()


def test_read_line_backspace_on_empty_buffer_is_a_noop():
    io_obj, out, fds = _make(ac.DELETE + ac.DELETE + b"ok" + ac.RETURN)
    result = read_line(io_obj)
    _close(fds)
    assert result == "ok"


def test_read_line_escape_returns_cancelled():
    io_obj, out, fds = _make(ac.ESCAPE)
    result = read_line(io_obj)
    _close(fds)
    assert result is CANCELLED


def test_read_line_password_mode_echoes_asterisks_not_the_characters():
    io_obj, out, fds = _make(b"secret" + ac.RETURN)
    result = read_line(io_obj, password=True)
    _close(fds)
    assert result == "secret"
    assert b"secret" not in out.getvalue()
    assert b"*" * 6 in out.getvalue()


def test_read_line_initial_value_is_prefilled_and_editable():
    io_obj, out, fds = _make(ac.DELETE + ac.DELETE + b"Z" + ac.RETURN)
    result = read_line(io_obj, initial="abc")
    _close(fds)
    assert result == "aZ"


def test_read_line_ignores_cursor_keys_and_tab():
    io_obj, out, fds = _make(bytes([28, 29, 127]) + b"ok" + ac.RETURN)
    result = read_line(io_obj)
    _close(fds)
    assert result == "ok"


def test_return_byte_is_155_not_13():
    assert ac.RETURN == bytes([155])
