from unittest.mock import MagicMock

from bi_terminal.core.errors import APIError, ImageFileNotFoundError
from bi_terminal.renderers.textual.screens import (
    ActionMenuTextualScreen,
    ConfirmTextualScreen,
    FormScreen,
    ListPickerTextualScreen,
    TextPromptTextualScreen,
)

from ._helpers import (
    fill_form_fields,
    make_app,
    make_cfg,
    run,
    wait_for,
    wait_for_exit,
    wait_for_menu_titled,
    wait_for_screen_type,
)


def _client_with_bins(bins):
    client = MagicMock()
    client.get_item_count.return_value = {"number": len(bins)}
    client.get_bins_by_user.return_value = {"bins": bins}
    return client


def test_my_bins_empty_shows_new_bin_affordance_not_an_error():
    async def _body():
        client = _client_with_bins([])
        app = make_app(client=client)
        async with app.run_test() as pilot:
            await wait_for_menu_titled(pilot, "Bin Inventory")
            await pilot.press("b")
            screen = await wait_for_screen_type(pilot, ListPickerTextualScreen)
            assert screen.spec.title == "My Bins"
            assert screen.spec.extra_lines == ["You have no bins yet."]
            names = [c.name for c in screen.spec.choices]
            assert "+ New Bin" in names
            assert "<- Back" in names
            await pilot.press("escape")
            await wait_for_menu_titled(pilot, "Bin Inventory")
            await pilot.press("x")
            await wait_for_exit(app)

    run(_body)


def test_bins_menu_404_is_treated_as_empty_not_an_error():
    """The unified core.policy.EMPTY_ON_404 fix taking effect for real."""

    async def _body():
        client = MagicMock()
        client.get_item_count.return_value = {"number": 0}
        client.get_bins_by_user.side_effect = APIError("not found", status_code=404)
        app = make_app(client=client)
        async with app.run_test() as pilot:
            await wait_for_menu_titled(pilot, "Bin Inventory")
            await pilot.press("b")
            screen = await wait_for_screen_type(pilot, ListPickerTextualScreen)
            assert screen.spec.extra_lines == ["You have no bins yet."]  # not an error notify
            await pilot.press("escape")
            await wait_for_menu_titled(pilot, "Bin Inventory")
            await pilot.press("x")
            await wait_for_exit(app)

    run(_body)


def test_create_bin_success():
    async def _body():
        client = _client_with_bins([])
        client.create_bin.return_value = {"bin": {"id": "b1", "binName": "Shelf A"}}
        app = make_app(client=client)
        async with app.run_test() as pilot:
            await wait_for_menu_titled(pilot, "Bin Inventory")
            await pilot.press("w")  # New Bin shortcut
            screen = await wait_for_screen_type(pilot, FormScreen)
            fill_form_fields(screen, {"bin_name": "Shelf A"})
            await pilot.press("ctrl+s")
            await wait_for_menu_titled(pilot, "Bin Inventory")  # back to main after create
            await pilot.press("x")
            await wait_for_exit(app)
        client.create_bin.assert_called_once()
        assert client.create_bin.call_args.kwargs["bin_name"] == "Shelf A"

    run(_body)


def test_create_bin_blank_name_stays_on_form():
    async def _body():
        client = _client_with_bins([])
        app = make_app(client=client)
        async with app.run_test() as pilot:
            await wait_for_menu_titled(pilot, "Bin Inventory")
            await pilot.press("w")
            screen = await wait_for_screen_type(pilot, FormScreen)
            await pilot.press("ctrl+s")  # bin_name left blank
            await pilot.pause(0.1)
            assert isinstance(pilot.app.screen, FormScreen)  # did not dismiss
            fill_form_fields(pilot.app.screen, {"bin_name": "Shelf B"})
            await pilot.press("ctrl+s")
            await wait_for_menu_titled(pilot, "Bin Inventory")
            await pilot.press("x")
            await wait_for_exit(app)
        client.create_bin.assert_called_once()

    run(_body)


def test_create_bin_image_not_found_retry_then_cancel():
    """core.policy.submit_with_image_retry's retry loop, driven through the
    real TextPromptTextualScreen — user is asked to re-enter a path, and
    pressing Esc there gives up the retry (matches bi_python's
    `_ask_retry_image_path` returning None on cancel)."""

    async def _body():
        client = _client_with_bins([])
        client.create_bin.side_effect = ImageFileNotFoundError("/no/such/file.png")
        app = make_app(client=client)
        async with app.run_test() as pilot:
            await wait_for_menu_titled(pilot, "Bin Inventory")
            await pilot.press("w")
            screen = await wait_for_screen_type(pilot, FormScreen)
            fill_form_fields(screen, {"bin_name": "Shelf C", "image_path": "/no/such/file.png"})
            await pilot.press("ctrl+s")
            prompt = await wait_for_screen_type(pilot, TextPromptTextualScreen)
            assert "Image file not found" not in prompt.spec.prompt  # prompt text is the retry ask, not the error
            await pilot.press("escape")  # give up the retry
            await wait_for_menu_titled(pilot, "Bin Inventory")
            await pilot.press("x")
            await wait_for_exit(app)
        assert client.create_bin.call_count == 1  # gave up after first failure, no retry attempted

    run(_body)


def test_bin_detail_delete_with_confirm():
    async def _body():
        bin_row = {"id": "b1", "binName": "Shelf A", "items": []}
        client = _client_with_bins([bin_row])
        app = make_app(client=client)
        async with app.run_test() as pilot:
            await wait_for_menu_titled(pilot, "Bin Inventory")
            await pilot.press("b")
            picker = await wait_for_screen_type(pilot, ListPickerTextualScreen)
            await pilot.press("enter")  # first (only real) choice is the bin itself
            detail = await wait_for_menu_titled(pilot, "Shelf A")
            await pilot.press("d")  # Delete Bin shortcut
            confirm = await wait_for_screen_type(pilot, ConfirmTextualScreen)
            await pilot.press("y")
            await wait_for(
                pilot,
                lambda: isinstance(pilot.app.screen, ListPickerTextualScreen)
                and pilot.app.screen.spec.title == "My Bins",
                "My Bins list (post-delete)",
            )
            await pilot.press("escape")
            await wait_for_menu_titled(pilot, "Bin Inventory")
            await pilot.press("x")
            await wait_for_exit(app)
        client.delete_bin.assert_called_once_with("b1")

    run(_body)
