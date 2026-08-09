"""Raw I/O for the ATASCII door renderer.

Structurally identical to renderers/petscii/io.py: no escape-sequence
disambiguation needed (ATASCII, like PETSCII, uses single control bytes
only — confirmed against Wikipedia's ATASCII article; the real Atari ESC
key's "quote the next character literally" role is a local screen-editor
convenience on real hardware, not a network-protocol prefix — nothing here
resembles ANSI's CSI). Binary throughout for the same UTF-8-corruption
reason already proven during the PETSCII increment.
"""

import os
import select
import termios
import tty
from contextlib import contextmanager
from typing import Any, Optional, Union

from ...specs.base import CANCELLED
from . import atascii_codes as ac
from .sanitize import to_atascii_text

_CURSOR_KEYS = {
    28: "up",
    29: "down",
    30: "left",
    31: "right",
}

# ATASCII's own control-code table literally NAMES byte 27 "Escape" --
# higher confidence than PETSCII's 0x1B guess (which wasn't in that
# protocol's table at all), but still genuinely unverified against a real
# ATASCII-capable client (none was available this session either). Same for
# 155 as ATASCII's own canonical end-of-line marker -- confirmed as the
# protocol's own definition, not borrowed from ASCII's 13, but still not
# live-tested. Confirm/adjust once Daniel has VICE/Altirra or SyncTERM's
# ATASCII mode available.
ESCAPE_BYTE = 27
RETURN_BYTE = 155
DELETE_BYTE = 126  # Atari's actual backspace-role key (not 254, "Delete Character")
TAB_BYTE = 127


class AtasciiKeyReader:
    """Reads and normalizes one logical keypress at a time. No pushback
    buffer needed (unlike renderers/ansi/io.py's KeyReader) — there's no
    multi-byte sequence to disambiguate in raw ATASCII, same as PETSCII."""

    def __init__(self, fd: int) -> None:
        self.fd = fd

    def read_key(self, timeout: Optional[float] = None) -> Optional[str]:
        r, _, _ = select.select([self.fd], [], [], timeout)
        if not r:
            return None
        b = os.read(self.fd, 1)
        if not b:
            return None
        n = b[0]
        if n in _CURSOR_KEYS:
            return _CURSOR_KEYS[n]
        if n == RETURN_BYTE:
            return "enter"
        if n == DELETE_BYTE:
            return "backspace"
        if n == ESCAPE_BYTE:
            return "escape"
        if n == TAB_BYTE:
            return "tab"
        if n == 3:
            return "ctrl+c"
        try:
            return bytes([n]).decode("ascii")
        except UnicodeDecodeError:
            return None  # some other ATASCII control byte we don't handle — ignore


class AtasciiIO:
    """Combines an AtasciiKeyReader (input) with binary output writing, plus
    optional local-terminal raw-mode setup for interactive testing.
    `out_stream` must accept bytes — same binary-throughout requirement as
    renderers/petscii/io.py's PetsciiIO, for the same reason."""

    def __init__(self, in_fd: int, out_stream) -> None:
        self.in_fd = in_fd
        self.out = out_stream
        self.keys = AtasciiKeyReader(in_fd)

    def write_raw(self, data: bytes) -> None:
        self.out.write(data)
        self.out.flush()

    def write_text(self, text: str) -> None:
        self.write_raw(to_atascii_text(text))

    def read_key(self, timeout: Optional[float] = None) -> Optional[str]:
        return self.keys.read_key(timeout)

    @contextmanager
    def maybe_raw_mode(self):
        """Same tty-detection pattern as AnsiIO/PetsciiIO — only sets raw
        mode when in_fd is actually a local tty (interactive testing); a
        no-op for a real door's already-raw stdin."""
        if not os.isatty(self.in_fd):
            yield
            return
        old = termios.tcgetattr(self.in_fd)
        try:
            tty.setraw(self.in_fd)
            yield
        finally:
            termios.tcsetattr(self.in_fd, termios.TCSADRAIN, old)


def read_line(io: AtasciiIO, password: bool = False, initial: str = "") -> Union[str, Any]:
    """Line editing built on AtasciiIO.read_key — same shape as the
    PETSCII/ANSI renderers' read_line. Backspace-erase uses ATASCII's own
    confirmed CURSOR_LEFT control byte (30), same "erase by moving back,
    printing a space, moving back again" technique as PETSCII's read_line,
    not ASCII's 0x08 (undefined in ATASCII)."""
    buf = list(initial)
    io.write_text(("*" * len(buf)) if password else "".join(buf))
    while True:
        key = io.read_key()
        if key == "enter":
            io.write_raw(ac.RETURN)
            return "".join(buf)
        if key in ("escape", "ctrl+c"):
            io.write_raw(ac.RETURN)
            return CANCELLED
        if key == "backspace":
            if buf:
                buf.pop()
                io.write_raw(ac.CURSOR_LEFT + b" " + ac.CURSOR_LEFT)
            continue
        if key in (None, "up", "down", "left", "right", "tab"):
            continue
        buf.append(key)
        io.write_text("*" if password else key)
