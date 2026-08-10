"""Console-script entry point: `bi-terminal-ansi`.

Text-only ANSI door (README "Sequencing", step 4) — stdio-based (Synchronet
"Standard" I/O door mode), no DOOR32.SYS/Socket-mode wiring yet (that's
real, separate follow-up work — see renderers/ansi/door32.py's stub).

**Fixed 2026-08-10, real live-reported bug:** this used to share
~/.binventory/config.json with the Textual renderer (same login) -- this
module's own docstring used to flag it as a known, deliberate limitation
"wrong for a real multi-user BBS deployment," and it did in fact bite: one
caller's login leaked straight to the next caller's connection. Now uses
config.door_cfg() (never reads/writes identity, only the non-sensitive
base_url) and AppDriver(persist_config=False) via AnsiApp, so this process
never touches disk at all -- every connection starts logged out. See
driver.py's AppDriver.__init__ docstring for the full design, including why
this is also the complete answer to concurrent callers.
"""

import sys

from .core import config
from .core.api import BinInventoryAPI
from .renderers.ansi.app import AnsiApp
from .renderers.ansi.io import AnsiIO


def main() -> None:
    cfg = config.door_cfg()
    client = BinInventoryAPI(base_url=cfg["base_url"])
    io = AnsiIO(sys.stdin.fileno(), sys.stdout)
    with io.maybe_raw_mode():
        AnsiApp(cfg, client, io, persist_config=False).run()


if __name__ == "__main__":
    main()
