"""BiTerminalTextualApp — the tracer-bullet's Textual App.

Drives exactly one screen (the main menu) through TextualRenderer, to prove
the sync-Renderer/async-Textual bridge end to end. Not yet the full app —
see README "Sequencing", step 3 for the full ~15-screen port that replaces
this with a real core.flow-driven dispatch loop and a real cfg/API client.
"""

from textual.app import App

from ...core.flow import GlobalNavigate
from ...specs.base import CANCELLED
from ...specs.menus import main_menu_spec
from .renderer import TextualRenderer


class BiTerminalTextualApp(App):
    def on_mount(self) -> None:
        self.dark = True
        self.renderer = TextualRenderer(self)
        self.run_worker(self._run_flow, thread=True, exclusive=True)

    def _run_flow(self) -> None:
        """Runs on a real OS thread (Textual's thread-worker pool), per the
        tracer-bullet plan — this is what makes push_screen_wait usable
        inside TextualRenderer.show_action_menu below.

        NOT named `_driver` — Textual's own App sets `self._driver` as an
        instance attribute internally (the actual terminal I/O driver, e.g.
        HeadlessDriver in tests), which silently shadows a same-named method
        instead of raising — confirmed the hard way here (a bound method
        named `_driver` got shadowed, and `run_worker` ended up trying to
        thread-run the HeadlessDriver instance itself, failing with
        "Unsupported attempt to run a thread worker"). This exact gotcha was
        already documented in bi_python's own project memory from its
        Textual conversion — worth remembering permanently for this repo
        too, not just bi_python."""
        spec = main_menu_spec("5")
        value = self.renderer.show_action_menu(spec)

        if isinstance(value, GlobalNavigate):
            self.renderer.notify(f"Global nav to {value.dest} (not wired yet)")
        elif value is CANCELLED:
            self.renderer.notify("Cancelled")
        else:
            self.renderer.notify(f"You picked: {value}")

        self.call_from_thread(self.exit, value)
