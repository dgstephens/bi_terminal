"""Console-script entry point: `bi-terminal-atascii`.

Atari 8-bit door (README "Sequencing", step 6) — stdio-based, same shape as
entry_ansi.py/entry_petscii.py. **`sys.stdout.buffer` is load-bearing, not
stylistic**: plain `sys.stdout` defaults to UTF-8 text encoding, which
would silently double-encode every ATASCII control byte above 0x7F (the
same corruption empirically confirmed during the PETSCII increment — see
renderers/atascii/atascii_codes.py). `AtasciiIO` is binary throughout for
exactly this reason.

Real ATASCII client verification (SyncTERM/VICE/Altirra) is a real
follow-up, not done in this increment — see renderers/atascii/README.md for
the socat/nc bridge that makes that a zero-setup "point the client at this
port" moment whenever a client is available.

**Fixed 2026-08-10, real live-reported bug:** used to share
~/.binventory/config.json with the Textual renderer, so one caller's login
leaked to the next caller's connection — see entry_ansi.py's docstring and
driver.py's AppDriver.__init__ docstring for the full story. Uses
config.door_cfg() + AppDriver(persist_config=False) now, same fix as ANSI.
"""

import sys

from .core import config
from .core.api import BinInventoryAPI
from .renderers.atascii.app import AtasciiApp
from .renderers.atascii.io import AtasciiIO


def main() -> None:
    cfg = config.door_cfg()
    client = BinInventoryAPI(base_url=cfg["base_url"])
    io = AtasciiIO(sys.stdin.fileno(), sys.stdout.buffer)
    with io.maybe_raw_mode():
        AtasciiApp(cfg, client, io, persist_config=False).run()


if __name__ == "__main__":
    main()
