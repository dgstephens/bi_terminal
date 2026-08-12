"""Console-script entry point: `bi-terminal-petscii-charbrowser`.

A live diagnostic tool, NOT part of the normal Binventory door flow — see
renderers/petscii/char_browser.py's module docstring for the full story
(verifying real byte values for PETSCII's block/shading graphic characters
against an actual SyncTERM/Synchronet connection, after the 2026-08-12
tiered-detail image experiment shipped a wrong glyph guess and had to be
reverted).

Deliberately the smallest possible entry point: no config.door_cfg(), no
BinInventoryAPI, no ~/.binventory/config.json access at all — this tool
never touches Binventory's backend or config in any way, matching
char_browser.py's own "smallest possible surface" design. Same
sys.stdout.buffer / binary-throughout requirement as entry_petscii.py, for
the same reason (PetsciiIO is binary throughout; a text-mode stream would
double-encode any control byte above 0x7F via UTF-8 — see
petscii_codes.py's module docstring).

**Debug logging (2026-08-12), always-on here, unlike entry_petscii.py's
opt-in BI_TERMINAL_PETSCII_DEBUG_LOG:** real, live-reported bug the same
day this tool shipped — after the pacing fix (see char_browser.py's run()
docstring), Daniel's connection got stuck redrawing page 1 three times
then disconnected, meaning his keypresses weren't being recognized as
"next page" for some still-unknown reason. Rather than ask him to
reconstruct exact keypresses again (established genuinely unreliable for
him — see this project's own memory on his dyslexia), this tool now always
logs every raw byte it receives and what key it resolved to (via
PetsciiKeyReader's existing, already-built logging — just needed a path
wired through here) plus every outbound row, to
~/petscii_charbrowser_debug.log. Always-on rather than opt-in specifically
because this whole entry point IS a diagnostic tool already (unlike the
real door, there's no production-noise concern), and reading the log
directly off this machine (it hosts both bi_terminal and Synchronet) needs
zero extra steps from Daniel — same technique already used successfully to
find a real Python traceback in Synchronet's own sbbs.log.
"""

import os
import sys
import time

from .renderers.petscii.char_browser import run
from .renderers.petscii.io import PetsciiIO

_DEFAULT_DEBUG_LOG = os.path.expanduser("~/petscii_charbrowser_debug.log")


def main() -> None:
    debug_log_path = os.environ.get("BI_TERMINAL_PETSCII_CHARBROWSER_DEBUG_LOG", _DEFAULT_DEBUG_LOG)
    try:
        # A session marker, not load-bearing -- lets repeated connection
        # attempts in the same log file be told apart at a glance. Never
        # allowed to crash the tool if the log path isn't writable for some
        # reason (same "a debug log must never be able to crash or block
        # the door" principle as PetsciiIO's own _log()/_log_output()).
        with open(debug_log_path, "a") as f:
            f.write(f"\n=== new connection {time.time():.3f} ===\n")
    except Exception:
        pass
    io = PetsciiIO(sys.stdin.fileno(), sys.stdout.buffer, debug_log_path=debug_log_path)
    with io.maybe_raw_mode():
        run(io)


if __name__ == "__main__":
    main()
