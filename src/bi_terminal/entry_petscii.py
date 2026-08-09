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
"""

import sys

from .core import config
from .core.api import BinInventoryAPI
from .renderers.petscii.app import PetsciiApp
from .renderers.petscii.io import PetsciiIO


def main() -> None:
    cfg = config.load()
    client = BinInventoryAPI(
        base_url=cfg.get("base_url", config.DEFAULT_URL),
        token=cfg.get("token"),
    )
    io = PetsciiIO(sys.stdin.fileno(), sys.stdout.buffer)
    with io.maybe_raw_mode():
        PetsciiApp(cfg, client, io).run()


if __name__ == "__main__":
    main()
