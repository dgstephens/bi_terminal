"""PetsciiApp — thin wiring around the shared AppDriver for the C64 door.

Same shape as renderers/ansi/app.py: no threading (PETSCII I/O is already
synchronous, nothing to protect from blocking), no on_global_navigate hook
(a linear print-based UI has no persistent screen stack to unwind — the
exception unwind through Python's own call stack inside driver.run() is the
entire mechanism).
"""

from ...core.api import BinInventoryAPI
from ...driver import AppDriver
from .io import PetsciiIO
from .renderer import PetsciiRenderer


class PetsciiApp:
    def __init__(
        self, cfg: dict, client: BinInventoryAPI, io: PetsciiIO, persist_config: bool = True
    ) -> None:
        self.io = io
        self.renderer = PetsciiRenderer(io)
        self.driver = AppDriver(
            cfg,
            client,
            self.renderer,
            on_exit=lambda: io.write_text("\rGoodbye!\r"),
            persist_config=persist_config,
        )

    def run(self) -> None:
        self.driver.run()
