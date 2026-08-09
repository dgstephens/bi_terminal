"""BiTerminalTextualApp — thin Textual-specific wiring around the shared
AppDriver (see ../../driver.py).

All the actual flow-orchestration logic (login, bins, items, search, shared,
profile, settings) used to live here as ~700 lines of methods; it moved to
driver.py once building the ANSI door renderer made clear that none of it
was Textual-specific — it only ever called self.renderer.show_*/notify,
self.client.*, and self.cfg. This file now holds exactly the two things
that ARE genuinely Textual-specific: bridging AppDriver's two hooks
(on_global_navigate / on_exit) into Textual's call_from_thread/screen-stack
machinery, and starting the driver on a thread worker (proven necessary in
the tracer-bullet increment — push_screen_wait requires Textual's
active_worker contextvar, only set on threads Textual's own worker
machinery started).
"""

from textual.app import App

from ...core.api import BinInventoryAPI
from ...driver import AppDriver
from .renderer import TextualRenderer


class BiTerminalTextualApp(App):
    def __init__(self, cfg: dict, client: BinInventoryAPI):
        super().__init__()
        self.cfg = cfg
        self.client = client

    def on_mount(self) -> None:
        self.dark = True
        self.renderer = TextualRenderer(self)
        self.driver = AppDriver(
            self.cfg,
            self.client,
            self.renderer,
            on_global_navigate=lambda: self.call_from_thread(self._pop_all_screens),
            on_exit=lambda: self.call_from_thread(self.exit),
        )
        # NOT named `_driver` — Textual's own App sets self._driver as an
        # instance attribute internally (the actual terminal I/O driver),
        # which silently shadows a same-named method instead of raising.
        # Confirmed the hard way in the tracer-bullet increment; the
        # attribute name `self.driver` above is fine (no leading
        # underscore, doesn't collide with Textual's private `_driver`).
        self.run_worker(self.driver.run, thread=True, exclusive=True)

    async def _pop_all_screens(self) -> None:
        while len(self.screen_stack) > 1:
            await self.pop_screen()


def main() -> None:
    from ...core import config

    cfg = config.load()
    client = BinInventoryAPI(
        base_url=cfg.get("base_url", config.DEFAULT_URL),
        token=cfg.get("token"),
    )
    BiTerminalTextualApp(cfg, client).run()


if __name__ == "__main__":
    main()
