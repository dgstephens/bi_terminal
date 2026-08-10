"""Raw I/O for the generic ANSI door renderer.

KeyReader's read_key() design (select-timeout peek + one-byte pushback to
disambiguate a lone Escape from a CSI arrow-key sequence) was prototyped and
empirically verified against a plain os.pipe() — the same code path a real
Standard I/O door process uses (its stdin is a pipe/socket, not a local
tty) — before being written here. The first prototype had a real bug: it
peeked one byte past ESC to check for `[`, and silently discarded that byte
when it wasn't `[` — e.g. Escape immediately followed by a shortcut letter
would eat the letter. Fixed with the one-byte pushback buffer below; see the
plan that produced this file for the 11 verification cases, including the
exact scenario the first prototype got wrong.
"""

import os
import select
import termios
import tty
from contextlib import contextmanager
from typing import Any, Optional, Union

from ...specs.base import CANCELLED
from .sanitize import to_ansi_text

_ARROW_KEYS = {"A": "up", "B": "down", "C": "right", "D": "left"}


class KeyReader:
    """Reads and normalizes one logical keypress at a time from a raw byte
    stream (a pipe, socket, or already-raw-mode tty fd)."""

    def __init__(self, fd: int) -> None:
        self.fd = fd
        self._pending: Optional[bytes] = None

    def _read_byte(self, timeout: Optional[float]) -> Optional[bytes]:
        if self._pending is not None:
            b, self._pending = self._pending, None
            return b
        r, _, _ = select.select([self.fd], [], [], timeout)
        if not r:
            return None
        b = os.read(self.fd, 1)
        return b if b else None

    def read_key(self, timeout: Optional[float] = None) -> Optional[str]:
        """Returns a normalized key string ("a", "enter", "escape",
        "backspace", "tab", "ctrl+c", "up"/"down"/"left"/"right"), or None
        on timeout/EOF."""
        b = self._read_byte(timeout)
        if b is None:
            return None
        if b == b"\x1b":
            # Ambiguous: a lone Escape keypress, or the start of a CSI
            # sequence (arrow keys send ESC [ <letter> as one back-to-back
            # burst). Peek with a short timeout to disambiguate.
            b2 = self._read_byte(0.05)
            if b2 is None:
                return "escape"
            if b2 != b"[":
                self._pending = b2  # not a CSI sequence — give the byte back
                return "escape"
            b3 = self._read_byte(1.0)
            return _ARROW_KEYS.get(b3.decode(errors="replace") if b3 else "", "unknown-csi")
        if b in (b"\r", b"\n"):
            return "enter"
        if b in (b"\x7f", b"\x08"):
            return "backspace"
        if b == b"\t":
            return "tab"
        if b == b"\x03":
            return "ctrl+c"
        return b.decode(errors="replace")


class AnsiIO:
    """Combines a KeyReader (input) with output writing, plus optional
    local-terminal raw-mode setup for interactive testing."""

    def __init__(self, in_fd: int, out_stream) -> None:
        self.in_fd = in_fd
        self.out = out_stream
        self.keys = KeyReader(in_fd)

    def write(self, text: str) -> None:
        # Sanitized before writing -- a real, live-reported bug (2026-08-10):
        # a bare Python str with no sanitization means any non-ASCII
        # character (app text does contain a few, e.g. an em dash) gets
        # UTF-8-encoded by the underlying text stream and garbles on a real
        # CP437 ANSI/BBS terminal. See sanitize.py's module docstring --
        # safe to run over the whole string including embedded CSI codes.
        text = to_ansi_text(text)
        # Translate bare \n to \r\n — raw mode gets no free NL->CRLF
        # translation from the tty driver once we're doing manual cursor
        # positioning, and a real door's output goes straight to a
        # socket/pipe, not a local cooked-mode tty at all.
        self.out.write(text.replace("\n", "\r\n"))
        self.out.flush()

    def read_key(self, timeout: Optional[float] = None) -> Optional[str]:
        return self.keys.read_key(timeout)

    @contextmanager
    def maybe_raw_mode(self):
        """Sets the local terminal to raw mode ONLY when in_fd is actually a
        tty (Daniel running this directly in his own terminal for local
        testing). A real Standard I/O door's stdin is already a raw byte
        stream relayed by the BBS — no local tty to set raw there, so this
        is correctly a no-op in that context."""
        if not os.isatty(self.in_fd):
            yield
            return
        old = termios.tcgetattr(self.in_fd)
        try:
            tty.setraw(self.in_fd)
            yield
        finally:
            termios.tcsetattr(self.in_fd, termios.TCSADRAIN, old)


def read_line(io: AnsiIO, password: bool = False, initial: str = "") -> Union[str, Any]:
    """Line editing built on AnsiIO.read_key: appends printable characters,
    Backspace removes the last one, Enter returns the accumulated string,
    Escape returns specs.base.CANCELLED. Password mode echoes '*' instead
    of the typed character. The shared building block for every
    text-entry field across every screen type."""
    buf = list(initial)
    io.write(("*" * len(buf)) if password else "".join(buf))
    while True:
        key = io.read_key()
        if key == "enter":
            io.write("\n")
            return "".join(buf)
        if key in ("escape", "ctrl+c"):
            io.write("\n")
            return CANCELLED
        if key == "backspace":
            if buf:
                buf.pop()
                io.write("\x08 \x08")  # erase the last echoed character
            continue
        if key in (None, "up", "down", "left", "right", "tab", "unknown-csi"):
            continue  # no cursor movement/history in this pass — ignored
        # a single printable character
        buf.append(key)
        io.write("*" if password else key)
