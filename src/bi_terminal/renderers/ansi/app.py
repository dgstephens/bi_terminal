"""AnsiApp — thin wiring around the shared AppDriver for the ANSI door.

Much simpler than the Textual renderer's app.py: ANSI I/O is already
synchronous (no event loop to protect), so there's no threading at all here
— driver.run() is just called directly. No on_global_navigate hook either:
a linear print-based UI has no persistent screen stack to unwind, so the
default no-op is exactly correct (the exception unwind through Python's own
call stack, inside driver.run(), is the entire mechanism).
"""

from ...core.api import BinInventoryAPI
from ...driver import AppDriver
from .io import AnsiIO
from .renderer import AnsiRenderer


class AnsiApp:
    def __init__(self, cfg: dict, client: BinInventoryAPI, io: AnsiIO) -> None:
        self.io = io
        self.renderer = AnsiRenderer(io)
        self.driver = AppDriver(
            cfg,
            client,
            self.renderer,
            on_exit=lambda: io.write("\nGoodbye!\n"),
        )

    def run(self) -> None:
        self.driver.run()
