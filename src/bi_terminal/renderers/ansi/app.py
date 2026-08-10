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
from .ansi_codes import RESET
from .io import AnsiIO
from .renderer import AnsiRenderer


def _say_goodbye(io: AnsiIO) -> None:
    # A real hard RESET here, not just BASE_SGR -- the door's screens
    # persist a navy background across every colored() span (see
    # ansi_codes.py's BASE_SGR), but that's only appropriate WHILE the door
    # is running. The caller's own terminal shouldn't stay tinted navy
    # after they disconnect from us.
    io.write(RESET + "\nGoodbye!\n")


class AnsiApp:
    def __init__(self, cfg: dict, client: BinInventoryAPI, io: AnsiIO) -> None:
        self.io = io
        self.renderer = AnsiRenderer(io)
        self.driver = AppDriver(
            cfg,
            client,
            self.renderer,
            on_exit=lambda: _say_goodbye(io),
        )

    def run(self) -> None:
        self.driver.run()
