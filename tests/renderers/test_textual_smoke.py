"""Smoke test for the real BiTerminalTextualApp (post full-parity port).

Supersedes the tracer-bullet's placeholder-app tests (which asserted
behavior specific to a zero-arg App with no cfg/client — obsolete now that
BiTerminalTextualApp takes real (cfg, client) and drives the full app.flow).
Still proves the same underlying thing the tracer bullet set out to prove —
a sync Renderer method driven from a Textual thread-worker correctly
bridges to a real screen and back — but against the real app, plus a basic
global-nav round trip now that the real _Bubble-catching driver exists.
"""

from unittest.mock import MagicMock

from bi_terminal.renderers.textual.screens import ActionMenuTextualScreen

from ._helpers import make_app, make_cfg, run, wait_for, wait_for_exit, wait_for_menu_titled


def test_app_boots_with_token_and_shows_main_menu():
    async def _body():
        client = MagicMock()
        client.get_item_count.return_value = {"number": 5}
        app = make_app(client=client, cfg=make_cfg())
        async with app.run_test() as pilot:
            screen = await wait_for_menu_titled(pilot, "Bin Inventory")
            assert "5 items" in screen.spec.title
            assert "daniel@example.com" in screen.spec.prompt
            await pilot.press("x")
            await wait_for_exit(app)
        assert not app.is_running

    run(_body)


def test_main_menu_global_nav_digit_jumps_to_bins_then_back_unwinds_stack():
    """Pressing '2' from the main menu jumps to Bins (a harmless self-jump
    in bi_python's terms, but proves the _Bubble/GlobalNavigate machinery
    round-trips through the real driver, not just the tracer bullet's single
    screen). From Bins, Esc returns to Main; base screen-stack depth is
    restored (Textual always keeps one implicit base screen, so baseline is
    len==1 here since nothing else was ever pushed permanently)."""

    async def _body():
        client = MagicMock()
        client.get_item_count.return_value = {"number": 0}
        client.get_bins_by_user.return_value = {"bins": []}
        app = make_app(client=client)
        async with app.run_test() as pilot:
            await wait_for_menu_titled(pilot, "Bin Inventory")
            # Capture the "at rest, showing one screen" depth here rather
            # than assuming a literal number — Textual keeps an implicit
            # base screen under everything (a real gotcha bi_python's own
            # project memory flagged: baseline is depth 2, not 1), so the
            # only robust check is "same depth as before," not a hardcoded
            # constant.
            baseline_depth = len(app.screen_stack)

            await pilot.press("2")
            from bi_terminal.renderers.textual.screens import ListPickerTextualScreen

            await wait_for(pilot, lambda: isinstance(pilot.app.screen, ListPickerTextualScreen), "Bins list")
            assert pilot.app.screen.spec.title == "My Bins"
            await pilot.press("escape")
            await wait_for_menu_titled(pilot, "Bin Inventory")
            assert len(app.screen_stack) == baseline_depth
            await pilot.press("x")
            await wait_for_exit(app)
        assert not app.is_running

    run(_body)
