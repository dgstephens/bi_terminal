from unittest.mock import MagicMock

from bi_terminal.renderers.textual.screens import ActionMenuTextualScreen, FormScreen, ListPickerTextualScreen

from ._helpers import fill_form_fields, make_app, run, wait_for_exit, wait_for_menu_titled, wait_for_screen_type

BIN = {"id": "b1", "binName": "Shelf A", "items": []}


def _client(search_items):
    client = MagicMock()
    client.get_item_count.return_value = {"number": 0}
    client.get_bins_by_user.return_value = {"bins": [BIN]}
    client.search_items.return_value = {"items": search_items}
    return client


def test_search_empty_query_notifies_and_stays_on_form():
    async def _body():
        client = _client([])
        app = make_app(client=client)
        async with app.run_test() as pilot:
            await wait_for_menu_titled(pilot, "Bin Inventory")
            await pilot.press("s")  # Search Items shortcut
            screen = await wait_for_screen_type(pilot, FormScreen)
            await pilot.press("ctrl+s")  # submit with query blank
            await pilot.pause(0.1)
            assert isinstance(pilot.app.screen, FormScreen)  # stayed on the search form
            await pilot.press("escape")
            await wait_for_menu_titled(pilot, "Bin Inventory")
            await pilot.press("x")
            await wait_for_exit(app)
        client.search_items.assert_not_called()

    run(_body)


def test_search_zero_results_notifies_and_stays_on_form():
    async def _body():
        client = _client([])
        app = make_app(client=client)
        async with app.run_test() as pilot:
            await wait_for_menu_titled(pilot, "Bin Inventory")
            await pilot.press("s")
            screen = await wait_for_screen_type(pilot, FormScreen)
            fill_form_fields(screen, {"query": "nonexistent"})
            await pilot.press("ctrl+s")
            await wait_for_screen_type(pilot, FormScreen)  # re-shown after "No results"
            await pilot.press("escape")
            await wait_for_menu_titled(pilot, "Bin Inventory")
            await pilot.press("x")
            await wait_for_exit(app)
        client.search_items.assert_called_once_with("nonexistent")

    run(_body)


def test_search_single_result_opens_detail_directly_no_picker():
    async def _body():
        item = {"id": "i1", "item": "Widget", "binId": {"id": "b1", "binName": "Shelf A"}, "images": []}
        client = _client([item])
        app = make_app(client=client)
        async with app.run_test() as pilot:
            await wait_for_menu_titled(pilot, "Bin Inventory")
            await pilot.press("s")
            screen = await wait_for_screen_type(pilot, FormScreen)
            fill_form_fields(screen, {"query": "widget"})
            await pilot.press("ctrl+s")
            detail = await wait_for_menu_titled(pilot, "Widget")
            assert not isinstance(detail, ListPickerTextualScreen)
            await pilot.press("b")  # item_detail's Back returns to a fresh search prompt
            await wait_for_screen_type(pilot, FormScreen)
            await pilot.press("escape")
            await wait_for_menu_titled(pilot, "Bin Inventory")
            await pilot.press("x")
            await wait_for_exit(app)

    run(_body)


def test_search_multiple_results_shows_picker():
    async def _body():
        items = [
            {"id": "i1", "item": "Widget A", "binId": {"id": "b1", "binName": "Shelf A"}, "images": []},
            {"id": "i2", "item": "Widget B", "binId": {"id": "b1", "binName": "Shelf A"}, "images": []},
        ]
        client = _client(items)
        app = make_app(client=client)
        async with app.run_test() as pilot:
            await wait_for_menu_titled(pilot, "Bin Inventory")
            await pilot.press("s")
            screen = await wait_for_screen_type(pilot, FormScreen)
            fill_form_fields(screen, {"query": "widget"})
            await pilot.press("ctrl+s")
            picker = await wait_for_screen_type(pilot, ListPickerTextualScreen)
            assert picker.spec.title == "Search : widget"
            assert len(picker.spec.choices) == 3  # 2 items + "<- New Search"
            await pilot.press("enter")
            await wait_for_menu_titled(pilot, "Widget A")
            await pilot.press("b")
            await wait_for_screen_type(pilot, FormScreen)
            await pilot.press("escape")
            await wait_for_menu_titled(pilot, "Bin Inventory")
            await pilot.press("x")
            await wait_for_exit(app)

    run(_body)
