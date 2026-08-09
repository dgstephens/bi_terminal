"""Headless round-trip test for the tracer bullet (README "Sequencing",
step 2): proves a sync Renderer.show_action_menu() call, driven from a
Textual thread-worker, correctly bridges to a real Textual screen, receives
a real simulated keypress, and returns the right dismissed value back to the
synchronous driver code — the one nontrivial technical risk flagged in
renderers/base.py, now verified rather than assumed.

Uses plain `asyncio.run()` per test rather than the pytest-asyncio plugin —
deliberately, to avoid adding a test-only dependency nothing else in this
repo needs; `App.run_test()` is a normal async context manager and works
fine driven that way.
"""

import asyncio

from bi_terminal.renderers.textual.app import BiTerminalTextualApp
from bi_terminal.renderers.textual.screens import ActionMenuTextualScreen
from bi_terminal.specs.base import CANCELLED


async def _wait_for_main_menu(pilot, timeout: float = 5.0):
    """The worker thread's call_from_thread(push_screen_wait, ...) call is
    asynchronous relative to run_test()'s own setup — poll rather than
    assume the screen is already up."""
    elapsed = 0.0
    step = 0.02
    while elapsed < timeout:
        if isinstance(pilot.app.screen, ActionMenuTextualScreen):
            return
        await pilot.pause(step)
        elapsed += step
    raise AssertionError("ActionMenuTextualScreen never appeared")


async def _wait_for_exit(app, timeout: float = 5.0):
    elapsed = 0.0
    step = 0.02
    while elapsed < timeout:
        if not app.is_running:
            return
        await asyncio.sleep(step)
        elapsed += step
    raise AssertionError("app never exited")


def test_pressing_exit_shortcut_returns_exit_value():
    async def _body():
        app = BiTerminalTextualApp()
        async with app.run_test() as pilot:
            await _wait_for_main_menu(pilot)
            await pilot.press("x")  # Exit's shortcut in main_menu_spec
            await _wait_for_exit(app)
        assert app.return_value == "exit"

    asyncio.run(_body())


def test_pressing_different_shortcut_returns_that_value_not_a_fixed_one():
    async def _body():
        app = BiTerminalTextualApp()
        async with app.run_test() as pilot:
            await _wait_for_main_menu(pilot)
            await pilot.press("b")  # "My Bins" shortcut, value "bins"
            await _wait_for_exit(app)
        assert app.return_value == "bins"

    asyncio.run(_body())


def test_pressing_escape_returns_cancelled_sentinel():
    async def _body():
        app = BiTerminalTextualApp()
        async with app.run_test() as pilot:
            await _wait_for_main_menu(pilot)
            await pilot.press("escape")
            await _wait_for_exit(app)
        assert app.return_value is CANCELLED

    asyncio.run(_body())


def test_main_menu_has_nav_disabled_so_digit_keys_are_plain_no_ops():
    # main_menu_spec sets nav_enabled=False (jumping to where you already
    # are is a no-op) — a digit press should NOT dismiss the screen at all,
    # unlike every other menu. Confirm the screen is still up afterward, then
    # clean up with a real shortcut so the test doesn't hang.
    async def _body():
        app = BiTerminalTextualApp()
        async with app.run_test() as pilot:
            await _wait_for_main_menu(pilot)
            await pilot.press("1")
            await pilot.pause(0.1)
            assert isinstance(pilot.app.screen, ActionMenuTextualScreen)
            assert not app.return_value  # nothing dismissed yet
            await pilot.press("x")
            await _wait_for_exit(app)
        assert app.return_value == "exit"

    asyncio.run(_body())
