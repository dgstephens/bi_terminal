"""DOOR32.SYS drop-file parsing — STUB, reserved for the ANSI door renderer.

Not built yet. When built: parses the DOOR32.SYS file Synchronet writes per
connection (comm handle/type, socket handle, BBS name, user info, time left,
and — relevant to bi_terminal — an `Emulation` field distinguishing
Ascii/Ansi/Avatar/RIP/MaxGraphics). Note DOOR32.SYS's Emulation field has no
PETSCII/ATASCII value and Synchronet's own terminal translation doesn't apply
to arbitrary door output, which is why PETSCII/ATASCII are separate door menu
entries the user self-selects rather than something this module could ever
auto-detect (see README's architecture section).
"""


def parse_door32(path: str) -> dict:
    raise NotImplementedError("DOOR32.SYS parsing not yet built — see README Sequencing")
