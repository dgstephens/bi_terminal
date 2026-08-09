"""Raw I/O for the PETSCII door renderer.

Simpler than the ANSI renderer's KeyReader: PETSCII has no escape sequences
at all (confirmed against Synchronet's CTerm manual — every operation is a
single control byte), so there's no CSI-sequence disambiguation needed —
just a single-byte read + lookup table. Still uses select() for a clean
timeout-capable read, the same pattern proven for the ANSI renderer's
KeyReader (verified there against a plain os.pipe()).

Binary throughout (see petscii_codes.py's module docstring for why) —
PetsciiIO's out_stream must accept bytes, not str.
"""

import os
import select
import termios
import tty
from contextlib import contextmanager
from typing import Any, Optional, Union

from ...specs.base import CANCELLED
from . import petscii_codes
from .sanitize import to_petscii_text

_CURSOR_KEYS = {
    145: "up",
    17: "down",
    157: "left",
    29: "right",
}

# See the plan's finding #5: PETSCII's own control-code space (documented
# in petscii_codes.py) never uses 0x1B, and every mainstream terminal
# client's convention is to pass a literal Escape keypress through
# unchanged regardless of emulation mode — so 0x1B is the well-reasoned
# choice for "cancel," consistent with the ANSI renderer, but this is
# UNVERIFIED against a real PETSCII client (none was available this
# session) — flagged explicitly, not silently assumed. Confirm/adjust once
# Daniel has VICE or SyncTERM available.
ESCAPE_BYTE = 0x1B


class PetsciiKeyReader:
    """Reads and normalizes one logical keypress at a time. No pushback
    buffer needed (unlike renderers/ansi/io.py's KeyReader) — there's no
    multi-byte sequence to disambiguate in raw PETSCII."""

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
        if n == 13:
            return "enter"
        if n == 20:
            return "backspace"
        if n == ESCAPE_BYTE:
            return "escape"
        if n == 3:
            return "ctrl+c"
        if n == 9:
            return "tab"
        try:
            return bytes([n]).decode("ascii")
        except UnicodeDecodeError:
            return None  # some other PETSCII control byte we don't handle — ignore


class PetsciiIO:
    """Combines a PetsciiKeyReader (input) with binary output writing, plus
    optional local-terminal raw-mode setup for interactive testing.
    `out_stream` must accept bytes (e.g. sys.stdout.buffer, a raw socket,
    or a BytesIO) — never a text-mode stream, which would double-encode any
    control byte above 0x7F via Python's default UTF-8 (empirically
    confirmed during this project's own research; see petscii_codes.py)."""

    def __init__(self, in_fd: int, out_stream) -> None:
        self.in_fd = in_fd
        self.out = out_stream
        self.keys = PetsciiKeyReader(in_fd)

    def write_raw(self, data: bytes) -> None:
        self.out.write(data)
        self.out.flush()

    def write_text(self, text: str) -> None:
        self.write_raw(to_petscii_text(text))

    def read_key(self, timeout: Optional[float] = None) -> Optional[str]:
        return self.keys.read_key(timeout)

    @contextmanager
    def maybe_raw_mode(self):
        """Same tty-detection pattern as the ANSI renderer's AnsiIO — only
        sets raw mode when in_fd is actually a local tty (interactive
        testing); a no-op for a real door's already-raw stdin."""
        if not os.isatty(self.in_fd):
            yield
            return
        old = termios.tcgetattr(self.in_fd)
        try:
            tty.setraw(self.in_fd)
            yield
        finally:
            termios.tcsetattr(self.in_fd, termios.TCSADRAIN, old)


def read_line(io: PetsciiIO, password: bool = False, initial: str = "") -> Union[str, Any]:
    """Line editing built on PetsciiIO.read_key — same shape as the ANSI
    renderer's read_line, but backspace-erase uses PETSCII's own confirmed
    CURSOR_LEFT control byte (157), not ASCII's 0x08 (which isn't in
    PETSCII's control-code table at all and has no defined meaning there —
    a mistake caught while writing this, not copy-pasted from the ANSI
    version unchecked)."""
    buf = list(initial)
    io.write_text(("*" * len(buf)) if password else "".join(buf))
    while True:
        key = io.read_key()
        if key == "enter":
            io.write_raw(petscii_codes.RETURN)
            return "".join(buf)
        if key in ("escape", "ctrl+c"):
            io.write_raw(petscii_codes.RETURN)
            return CANCELLED
        if key == "backspace":
            if buf:
                buf.pop()
                io.write_raw(petscii_codes.CURSOR_LEFT + b" " + petscii_codes.CURSOR_LEFT)
            continue
        if key in (None, "up", "down", "left", "right", "tab"):
            continue  # no cursor movement/history in this pass — ignored
        buf.append(key)
        io.write_text("*" if password else key)
