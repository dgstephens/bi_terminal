"""Console-script entry point: `bi-terminal-petscii`.

Commodore 64 door (README "Sequencing", step 5) — stdio-based, same shape
as entry_ansi.py. **`sys.stdout.buffer` is load-bearing, not stylistic**:
plain `sys.stdout` defaults to UTF-8 text encoding, which would silently
double-encode every PETSCII control byte above 0x7F (empirically confirmed
during this project's own research — see renderers/petscii/petscii_codes.py)
and corrupt the output. `PetsciiIO` is binary throughout for exactly this
reason.

Real PETSCII client verification (SyncTERM/VICE) is a real follow-up, not
done in this increment — see renderers/petscii/README.md for the socat
bridge that makes that a zero-setup "point the client at this port" moment
whenever a client is available.

**Fixed 2026-08-10, real live-reported bug:** used to share
~/.binventory/config.json with the Textual renderer, so one caller's login
leaked to the next caller's connection — see entry_ansi.py's docstring and
driver.py's AppDriver.__init__ docstring for the full story. Uses
config.door_cfg() + AppDriver(persist_config=False) now, same fix as ANSI.

**Diagnostic env var (2026-08-10):** set BI_TERMINAL_PETSCII_DEBUG_LOG to a
writable file path to log every raw byte this door receives and what key
it resolved to — added to investigate a real, live-reported bug (cursor
keys + backspace not working through a real Synchronet BBS connection,
despite a direct byte capture proving SyncTERM sends exactly the bytes
this renderer's io.py already expects). Off by default; see
renderers/petscii/io.py's PetsciiKeyReader docstring for the full story.
Set this in the door's SCFG "Environment variable(s) to set" field (or
Command Line, if SCFG lets you export inline) for one real BBS session,
then read the file to see ground truth.
"""

import os
import sys

from .core import config
from .core.api import BinInventoryAPI
from .renderers.petscii.app import PetsciiApp
from .renderers.petscii.io import PetsciiIO


def main() -> None:
    cfg = config.door_cfg()
    client = BinInventoryAPI(base_url=cfg["base_url"])
    debug_log_path = os.environ.get("BI_TERMINAL_PETSCII_DEBUG_LOG")
    io = PetsciiIO(sys.stdin.fileno(), sys.stdout.buffer, debug_log_path=debug_log_path)
    with io.maybe_raw_mode():
        PetsciiApp(cfg, client, io, persist_config=False).run()


if __name__ == "__main__":
    main()
