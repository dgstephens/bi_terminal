from unittest.mock import MagicMock

from bi_terminal.renderers.textual.screens import ActionMenuTextualScreen, FormScreen, ListPickerTextualScreen

from ._helpers import fill_form_fields, make_app, run, wait_for, wait_for_exit, wait_for_menu_titled, wait_for_screen_type

BIN = {"id": "b1", "binName": "Shelf A", "items": []}


def _client_with_items(items, bins=(BIN,)):
    client = MagicMock()
    client.get_item_count.return_value = {"number": len(items)}
    client.get_items_by_user.return_value = {"items": items}
    client.get_bins_by_user.return_value = {"bins": list(bins)}
    return client


def test_create_item_uses_first_bin_by_default_and_succeeds():
    """The Bin combo field defaults to the first bin in the list (matching
    bi_python's preselect logic) without needing any manual interaction —
    proves the ComboFilterSelectField's default population works."""

    async def _body():
        client = _client_with_items([])
        client.create_item.return_value = {"thisItem": {"id": "i1", "item": "Widget"}}
        app = make_app(client=client)
        async with app.run_test() as pilot:
            await wait_for_menu_titled(pilot, "Bin Inventory")
            await pilot.press("n")  # New Item shortcut
            screen = await wait_for_screen_type(pilot, FormScreen)
            fill_form_fields(screen, {"item": "Widget"})
            await pilot.press("ctrl+s")
            await wait_for_menu_titled(pilot, "Bin Inventory")
            await pilot.press("x")
            await wait_for_exit(app)
        client.create_item.assert_called_once()
        assert client.create_item.call_args.kwargs["bin_id"] == "b1"
        assert client.create_item.call_args.kwargs["item"] == "Widget"

    run(_body)


def test_create_item_no_bins_shows_error_not_a_form():
    async def _body():
        client = _client_with_items([], bins=())
        app = make_app(client=client)
        async with app.run_test() as pilot:
            await wait_for_menu_titled(pilot, "Bin Inventory")
            await pilot.press("n")
            await wait_for_menu_titled(pilot, "Bin Inventory")  # notify + straight back, no form shown
            await pilot.press("x")
            await wait_for_exit(app)
        client.create_item.assert_not_called()

    run(_body)


def test_item_detail_shows_full_field_list_and_edits():
    async def _body():
        item = {
            "id": "i1",
            "item": "Widget",
            "binId": {"id": "b1", "binName": "Shelf A"},
            "prevBin": None,
            "images": [],
            "description": "A widget",
            "quantity": "3",
        }
        client = _client_with_items([item])
        client.get_items_by_bin.return_value = {"items": []}
        client.update_item.return_value = {
            "thisItem": {"id": "i1", "item": "Widget XL", "binId": "b1", "prevBin": None}
        }
        app = make_app(client=client)
        async with app.run_test() as pilot:
            await wait_for_menu_titled(pilot, "Bin Inventory")
            await pilot.press("i")  # My Items shortcut
            picker = await wait_for_screen_type(pilot, ListPickerTextualScreen)
            await pilot.press("enter")
            detail = await wait_for_menu_titled(pilot, "Widget")
            assert "Shelf A" in detail.spec.prompt  # Bin name shown via bin_name_from_item
            assert "A widget" in detail.spec.prompt
            await pilot.press("e")  # Edit Item
            form = await wait_for_screen_type(pilot, FormScreen)
            fill_form_fields(form, {"item": "Widget XL"})
            await pilot.press("ctrl+s")
            detail2 = await wait_for_menu_titled(pilot, "Widget XL")
            await pilot.press("b")  # Back -> returns to the My Items list (not straight
            # to main — item_detail's caller is all_items_menu's while loop, matching
            # bi_python's nested-loop structure exactly), one more Esc gets to main.
            await wait_for_screen_type(pilot, ListPickerTextualScreen)
            await pilot.press("escape")
            await wait_for_menu_titled(pilot, "Bin Inventory")
            await pilot.press("x")
            await wait_for_exit(app)
        client.update_item.assert_called_once()
        assert client.update_item.call_args.kwargs["item"] == "Widget XL"

    run(_body)


def test_move_back_to_prev_bin():
    async def _body():
        item = {
            "id": "i1",
            "item": "Widget",
            "binId": {"id": "b1", "binName": "Shelf A"},
            "prevBin": "b0",
            "images": [],
        }
        bins = [BIN, {"id": "b0", "binName": "Old Shelf", "items": []}]
        client = _client_with_items([item], bins=bins)
        client.update_item.return_value = {
            "thisItem": {"id": "i1", "item": "Widget", "binId": "b0", "prevBin": None}
        }
        app = make_app(client=client)
        async with app.run_test() as pilot:
            await wait_for_menu_titled(pilot, "Bin Inventory")
            await pilot.press("i")
            await wait_for_screen_type(pilot, ListPickerTextualScreen)
            await pilot.press("enter")
            detail = await wait_for_menu_titled(pilot, "Widget")
            # bi_python itself never resolves prevBin to a real name on a
            # FIRST view of an item straight from a list endpoint —
            # prevBin is always a raw ID string from every endpoint (see
            # core.models' docstring), only ever repopulated to {id,
            # binName} after an edit/move-back cycle mutates the in-memory
            # dict. So the initial label is the generic "previous bin"
            # fallback, not "Old Shelf" — this is faithful parity, not a
            # bug; confirmed by reading bi_python's app.py, which has the
            # exact same gap (never calls _repopulate_item_bin_refs before
            # first display, only after edit/move_prev).
            move_items = [item for item in detail.spec.items if item.value == "move_prev"]
            assert len(move_items) == 1
            assert "previous bin" in move_items[0].label
            await pilot.press("m")  # Move back to prev bin
            await wait_for(
                pilot,
                lambda: (
                    isinstance(pilot.app.screen, ActionMenuTextualScreen)
                    and pilot.app.screen is not detail
                    and "Widget" in pilot.app.screen.spec.title
                ),
                "item detail refreshed after move",
            )
            assert not any(item.value == "move_prev" for item in pilot.app.screen.spec.items)
            await pilot.press("b")  # Back -> returns to the My Items list, see note above
            await wait_for_screen_type(pilot, ListPickerTextualScreen)
            await pilot.press("escape")
            await wait_for_menu_titled(pilot, "Bin Inventory")
            await pilot.press("x")
            await wait_for_exit(app)
        client.update_item.assert_called_once()
        assert client.update_item.call_args.kwargs["bin_id"] == "b0"

    run(_body)
