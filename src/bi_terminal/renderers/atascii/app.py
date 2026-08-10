"""AtasciiApp — thin wiring around the shared AppDriver for the Atari 8-bit
door. Identical shape to renderers/petscii/app.py and renderers/ansi/app.py:
no threading (ATASCII I/O is already synchronous), no on_global_navigate
hook (a linear print-based UI has no persistent screen stack to unwind).
"""

from ...core.api import BinInventoryAPI
from ...driver import AppDriver
from . import atascii_codes as ac
from .io import AtasciiIO
from .renderer import AtasciiRenderer


def _say_goodbye(io: AtasciiIO) -> None:
    # NOT io.write_text("\rGoodbye!\r") — ASCII "\r" (13) is not a defined
    # ATASCII control code (confirmed: ATASCII's own RETURN is 155, and
    # 0-31 is reserved for low-level graphics), so it would render as a
    # stray graphics glyph on a real Atari instead of a line break. This
    # bug was caught by inspecting the actual bytes from a live nc bridge
    # test, not assumed away — PETSCII's equivalent line happens to be
    # correct only because PETSCII's own RETURN really is 13, a coincidence
    # that doesn't hold here.
    io.write_raw(ac.RETURN)
    io.write_text("Goodbye!")
    io.write_raw(ac.RETURN)


class AtasciiApp:
    def __init__(
        self, cfg: dict, client: BinInventoryAPI, io: AtasciiIO, persist_config: bool = True
    ) -> None:
        self.io = io
        self.renderer = AtasciiRenderer(io)
        self.driver = AppDriver(
            cfg,
            client,
            self.renderer,
            on_exit=lambda: _say_goodbye(io),
            persist_config=persist_config,
        )

    def run(self) -> None:
        self.driver.run()
