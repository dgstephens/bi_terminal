"""Textual Screen subclasses consuming bi_terminal.specs specs.

This is the tracer-bullet increment (see README "Sequencing", step 2): only
ActionMenuTextualScreen exists so far, proving the sync-Renderer/async-
Textual bridge on one screen type before the full ~15-screen port.
"""

from textual.screen import Screen
from textual.widgets import Static

from ...core.flow import NAV_TARGETS, GlobalNavigate
from ...specs.base import CANCELLED
from ...specs.fields import ActionMenuSpec


class ActionMenuTextualScreen(Screen):
    """Renders an ActionMenuSpec: single-keypress shortcuts dismiss
    immediately (no Enter needed), matching bi_python's ActionMenuScreen
    behavior and the contract documented on
    renderers.base.Renderer.show_action_menu."""

    def __init__(self, spec: ActionMenuSpec) -> None:
        super().__init__()
        self.spec = spec

    def compose(self):
        lines = [self.spec.title, ""]
        if self.spec.prompt:
            lines.append(self.spec.prompt)
            lines.append("")
        for item in self.spec.items:
            if item.separator:
                lines.append("─" * 20)
            else:
                lines.append(f"[{item.shortcut}] {item.label}")
        yield Static("\n".join(lines))

    def on_key(self, event) -> None:
        key = event.key
        if key in ("escape", "ctrl+c"):
            self.dismiss(CANCELLED)
            return
        if self.spec.nav_enabled and key in NAV_TARGETS:
            dest, _label = NAV_TARGETS[key]
            self.dismiss(GlobalNavigate(dest))
            return
        for item in self.spec.items:
            if item.separator or item.shortcut is None:
                continue
            if key.lower() == item.shortcut.lower():
                self.dismiss(item.value)
                return
