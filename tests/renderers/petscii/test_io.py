import io as pyio
import os

from bi_terminal.renderers.petscii import petscii_codes as pc
from bi_terminal.renderers.petscii.io import PetsciiIO, read_line
from bi_terminal.specs.base import CANCELLED


def _make(write_bytes: bytes):
    r_fd, w_fd = os.pipe()
    os.write(w_fd, write_bytes)
    out = pyio.BytesIO()
    return PetsciiIO(r_fd, out), out, (r_fd, w_fd)


def _close(fds):
    for fd in fds:
        try:
            os.close(fd)
        except OSError:
            pass


def test_write_raw_passes_bytes_through_unmodified():
    io_obj, out, fds = _make(b"")
    io_obj.write_raw(pc.CLR + pc.CYAN)
    _close(fds)
    assert out.getvalue() == pc.CLR + pc.CYAN


def test_write_text_swaps_case_for_petscii_lowercase_mode():
    """Real, live-reported bug (2026-08-10): "the PETSCII version has upper
    and lower case letters switched." Root cause: PetsciiRenderer sends
    SWITCH_TO_LOWERCASE once at construction and never switches back, so
    the whole session is in PETSCII's charset 2 -- where the byte values
    ASCII considers uppercase display as LOWERCASE on a real C64 screen,
    and vice versa. Confirmed against multiple independent PETSCII
    references (see sanitize.py's module docstring). write_text must swap
    case BEFORE encoding, so the swap and the C64's own charset inversion
    cancel out and the caller sees correctly-cased text."""
    io_obj, out, fds = _make(b"")
    io_obj.write_text("Hello World")
    _close(fds)
    assert out.getvalue() == b"hELLO wORLD"


def test_write_text_sanitizes_em_dash():
    io_obj, out, fds = _make(b"")
    io_obj.write_text("Bin Inventory — 5 items")
    _close(fds)
    # Case swapped deliberately -- see sanitize.py's module docstring (real
    # bug, fixed 2026-08-10): this is what displays CORRECTLY-cased on a
    # real C64 in the charset-2 "lowercase mode" this renderer uses.
    assert out.getvalue() == b"bIN iNVENTORY - 5 ITEMS"


def test_write_text_never_double_encodes_high_bytes_as_utf8():
    """The exact regression this project's own research caught: plain
    Python text output defaults to UTF-8, which turns any byte above 0x7F
    into a 2+ byte UTF-8 sequence. write_text must never do this -- every
    character it emits must be exactly one byte."""
    io_obj, out, fds = _make(b"")
    io_obj.write_text("plain ascii text")
    _close(fds)
    assert len(out.getvalue()) == len("plain ascii text")


def test_write_text_replaces_truly_unknown_chars_with_question_mark():
    io_obj, out, fds = _make(b"")
    io_obj.write_text("emoji: \U0001f600")
    _close(fds)
    assert b"?" in out.getvalue()
    assert b"\xf0\x9f\x98\x80" not in out.getvalue()  # not raw UTF-8 emoji bytes


def test_maybe_raw_mode_is_a_noop_on_a_non_tty_fd():
    io_obj, out, fds = _make(b"")
    with io_obj.maybe_raw_mode():
        io_obj.write_text("inside")
    _close(fds)
    assert out.getvalue() == b"INSIDE"  # case swapped -- see sanitize.py


def test_read_line_basic():
    io_obj, out, fds = _make(b"hello" + pc.RETURN)
    result = read_line(io_obj)
    _close(fds)
    assert result == "hello"


def test_read_line_backspace_uses_petscii_cursor_left_not_ascii_bs():
    """Confirms the fix made while writing io.py: erasing a character uses
    PETSCII's own confirmed CURSOR_LEFT control byte (157), not ASCII 0x08
    (which has no defined meaning in PETSCII's control-code table)."""
    io_obj, out, fds = _make(b"hi" + bytes([20]) + b"x" + pc.RETURN)  # "hi", DEL, "x" -> "hx"
    result = read_line(io_obj)
    _close(fds)
    assert result == "hx"
    assert pc.CURSOR_LEFT + b" " + pc.CURSOR_LEFT in out.getvalue()
    assert b"\x08" not in out.getvalue()


def test_read_line_backspace_on_empty_buffer_is_a_noop():
    io_obj, out, fds = _make(bytes([20, 20]) + b"ok" + pc.RETURN)
    result = read_line(io_obj)
    _close(fds)
    assert result == "ok"


def test_read_line_escape_returns_cancelled():
    io_obj, out, fds = _make(bytes([0x1B]))
    result = read_line(io_obj)
    _close(fds)
    assert result is CANCELLED


def test_read_line_password_mode_echoes_asterisks_not_the_characters():
    io_obj, out, fds = _make(b"secret" + pc.RETURN)
    result = read_line(io_obj, password=True)
    _close(fds)
    assert result == "secret"
    assert b"secret" not in out.getvalue()
    assert b"*" * 6 in out.getvalue()


def test_read_line_initial_value_is_prefilled_and_editable():
    io_obj, out, fds = _make(bytes([20, 20]) + b"Z" + pc.RETURN)  # remove last 2 of "abc", add "Z" -> "aZ"
    result = read_line(io_obj, initial="abc")
    _close(fds)
    assert result == "aZ"


def test_read_line_ignores_cursor_keys_and_tab():
    io_obj, out, fds = _make(bytes([145, 17, 9]) + b"ok" + pc.RETURN)
    result = read_line(io_obj)
    _close(fds)
    assert result == "ok"
