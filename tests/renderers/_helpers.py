"""Shared test helpers for the Textual renderer's headless regression suite.

Critical methodology note, carried over from bi_python's own project history
(a real incident there, not a hypothetical): a headless test that mocks the
API client but not core.config.save/load can overwrite the real
~/.binventory/config.json with mock data. `make_app()` below always builds
apps with an in-memory cfg dict, but any test whose code path calls
core.config.save (login, logout, settings, profile-email-change) MUST also
use `patched_config_save()` — it is NOT patched automatically just by using
make_app(), because config.save's module-level identity has to be patched
per-test via `unittest.mock.patch.object`, not baked into the app instance.
"""

import asyncio
from unittest.mock import MagicMock, patch

from bi_terminal.core import config as config_module
from bi_terminal.renderers.textual.app import BiTerminalTextualApp


def make_cfg(**overrides):
    cfg = {
        "base_url": "https://example.invalid/api",
        "token": "test-token",
        "userId": "u1",
        "email": "daniel@example.com",
        "image_mode": "none",
    }
    cfg.update(overrides)
    return cfg


def make_app(client=None, cfg=None):
    return BiTerminalTextualApp(cfg if cfg is not None else make_cfg(), client or MagicMock())


def patched_config_save():
    """Context manager patching core.config.save — see module docstring.
    Use as: `with patched_config_save() as save_mock: ...`"""
    return patch.object(config_module, "save")


def patched_config_load(return_value=None):
    return patch.object(config_module, "load", return_value=return_value or make_cfg())


async def wait_for(pilot, predicate, description: str, timeout: float = 5.0):
    elapsed = 0.0
    step = 0.02
    while elapsed < timeout:
        if predicate():
            return
        await pilot.pause(step)
        elapsed += step
    raise AssertionError(f"timed out waiting for: {description} (screen was {pilot.app.screen!r})")


async def wait_for_screen_type(pilot, screen_type, timeout: float = 5.0):
    await wait_for(
        pilot, lambda: isinstance(pilot.app.screen, screen_type), screen_type.__name__, timeout
    )
    return pilot.app.screen


async def wait_for_menu_titled(pilot, substring: str, timeout: float = 5.0):
    """Waits for an ActionMenuTextualScreen whose spec.title contains
    `substring` — several different menus are the same screen CLASS, so
    isinstance alone can't distinguish e.g. the login choice from the main
    menu."""
    from bi_terminal.renderers.textual.screens import ActionMenuTextualScreen

    def _match():
        s = pilot.app.screen
        return isinstance(s, ActionMenuTextualScreen) and substring in s.spec.title

    await wait_for(pilot, _match, f"ActionMenuTextualScreen titled ~{substring!r}", timeout)
    return pilot.app.screen


async def wait_for_exit(app, timeout: float = 5.0):
    elapsed = 0.0
    step = 0.02
    while elapsed < timeout:
        if not app.is_running:
            return
        await asyncio.sleep(step)
        elapsed += step
    raise AssertionError("app never exited")


def fill_form_fields(screen, values: dict) -> None:
    """Directly sets widget values for a FormScreen's fields by id, rather
    than simulating character-by-character typing — Input/Switch/TextArea's
    own typing behavior is Textual's to test, not ours; this exercises the
    actual field-to-widget wiring and action_save() validation for real,
    which is what these tests care about."""
    from textual.widgets import Switch, TextArea

    for name, value in values.items():
        widget = screen.query_one(f"#{name}")
        if isinstance(widget, Switch):
            widget.value = value
        elif isinstance(widget, TextArea):
            widget.text = value
        else:
            widget.value = value


def run(coro_fn):
    """asyncio.run wrapper — no pytest-asyncio dependency, matching the
    tracer-bullet increment's own approach."""
    asyncio.run(coro_fn())
