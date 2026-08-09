"""Console-script entry point: `bi-terminal-ansi`.

Text-only ANSI door (README "Sequencing", step 4) — stdio-based (Synchronet
"Standard" I/O door mode), no DOOR32.SYS/Socket-mode wiring yet (that's
real, separate follow-up work — see renderers/ansi/door32.py's stub).

**Known, deliberate limitation:** shares ~/.binventory/config.json with the
Textual renderer (same login) — correct for local single-user testing
(matches core/config.py's "shared across renderers on the same machine
deliberately" design), but wrong for a real multi-user BBS deployment,
where one shared login file across concurrent door sessions makes no
sense. Per-session config is real follow-up work for the DOOR32.SYS phase,
not solved here.
"""

import sys

from .core import config
from .core.api import BinInventoryAPI
from .renderers.ansi.app import AnsiApp
from .renderers.ansi.io import AnsiIO


def main() -> None:
    cfg = config.load()
    client = BinInventoryAPI(
        base_url=cfg.get("base_url", config.DEFAULT_URL),
        token=cfg.get("token"),
    )
    io = AnsiIO(sys.stdin.fileno(), sys.stdout)
    with io.maybe_raw_mode():
        AnsiApp(cfg, client, io).run()


if __name__ == "__main__":
    main()
