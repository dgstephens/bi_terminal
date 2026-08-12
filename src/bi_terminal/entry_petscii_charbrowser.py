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
"""

import sys

from .renderers.petscii.char_browser import run
from .renderers.petscii.io import PetsciiIO


def main() -> None:
    io = PetsciiIO(sys.stdin.fileno(), sys.stdout.buffer)
    with io.maybe_raw_mode():
        run(io)


if __name__ == "__main__":
    main()
