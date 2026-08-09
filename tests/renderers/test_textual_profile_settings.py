from unittest.mock import MagicMock

from bi_terminal.core.errors import ImageFileNotFoundError
from bi_terminal.renderers.base import ImageCapability
from bi_terminal.renderers.textual.screens import FormScreen, TextPromptTextualScreen

from ._helpers import fill_form_fields, make_app, make_cfg, patched_config_save, run, wait_for_exit, wait_for_menu_titled, wait_for_screen_type


def _client_with_user(user):
    client = MagicMock()
    client.get_item_count.return_value = {"number": 0}
    client.get_user.return_value = {"user": user}
    return client


def test_profile_edit_success():
    async def _body():
        user = {"name": "Daniel", "email": "d@example.com", "about": "", "showOnUsersPage": False}
        client = _client_with_user(user)
        client.update_user.return_value = {}
        app = make_app(client=client)
        with patched_config_save():
            async with app.run_test() as pilot:
                await wait_for_menu_titled(pilot, "Bin Inventory")
                await pilot.press("p")  # My Profile shortcut
                profile = await wait_for_menu_titled(pilot, "My Profile")
                assert "Daniel" in profile.spec.prompt
                await pilot.press("e")  # Edit Profile
                form = await wait_for_screen_type(pilot, FormScreen)
                fill_form_fields(form, {"about": "Retrocomputing enthusiast"})
                await pilot.press("ctrl+s")
                await wait_for_menu_titled(pilot, "My Profile")
                await pilot.press("b")
                await wait_for_menu_titled(pilot, "Bin Inventory")
                await pilot.press("x")
                await wait_for_exit(app)
        client.update_user.assert_called_once()
        assert client.update_user.call_args.kwargs["about"] == "Retrocomputing enthusiast"

    run(_body)


def test_profile_edit_has_image_retry_loop_unlike_bi_python():
    """The confirmed fix from the foundation increment: bi_python's
    edit_profile had NO image-not-found retry loop, unlike Bin/Item forms —
    an inconsistency fixed here since core.policy.submit_with_image_retry is
    now shared uniformly across all three."""

    async def _body():
        user = {"name": "Daniel", "email": "d@example.com", "about": "", "showOnUsersPage": False}
        client = _client_with_user(user)
        client.update_user.side_effect = ImageFileNotFoundError("/no/such/avatar.png")
        app = make_app(client=client)
        with patched_config_save():
            async with app.run_test() as pilot:
                await wait_for_menu_titled(pilot, "Bin Inventory")
                await pilot.press("p")
                await wait_for_menu_titled(pilot, "My Profile")
                await pilot.press("e")
                form = await wait_for_screen_type(pilot, FormScreen)
                fill_form_fields(form, {"image_path": "/no/such/avatar.png"})
                await pilot.press("ctrl+s")
                # A real retry prompt appears — proves the loop exists here now
                await wait_for_screen_type(pilot, TextPromptTextualScreen)
                await pilot.press("escape")  # give up the retry
                await wait_for_menu_titled(pilot, "My Profile")
                await pilot.press("b")
                await wait_for_menu_titled(pilot, "Bin Inventory")
                await pilot.press("x")
                await wait_for_exit(app)
        assert client.update_user.call_count == 1  # gave up after first failure

    run(_body)


def test_profile_email_change_saves_config():
    async def _body():
        user = {"name": "Daniel", "email": "old@example.com", "about": "", "showOnUsersPage": False}
        client = _client_with_user(user)
        client.update_user.return_value = {}
        cfg = make_cfg(email="old@example.com")
        app = make_app(client=client, cfg=cfg)
        with patched_config_save() as save_mock:
            async with app.run_test() as pilot:
                await wait_for_menu_titled(pilot, "Bin Inventory")
                await pilot.press("p")
                await wait_for_menu_titled(pilot, "My Profile")
                await pilot.press("e")
                form = await wait_for_screen_type(pilot, FormScreen)
                fill_form_fields(form, {"email": "new@example.com"})
                await pilot.press("ctrl+s")
                await wait_for_menu_titled(pilot, "My Profile")
                await pilot.press("b")
                await wait_for_menu_titled(pilot, "Bin Inventory")
                await pilot.press("x")
                await wait_for_exit(app)
            assert save_mock.called
        assert cfg["email"] == "new@example.com"

    run(_body)


def test_settings_change_persists_and_updates_live_renderer_capability():
    async def _body():
        client = MagicMock()
        client.get_item_count.return_value = {"number": 0}
        cfg = make_cfg(image_mode="none")
        app = make_app(client=client, cfg=cfg)
        with patched_config_save() as save_mock:
            async with app.run_test() as pilot:
                await wait_for_menu_titled(pilot, "Bin Inventory")
                assert app.renderer.image_capability == ImageCapability.NONE
                await pilot.press("t")  # Settings shortcut
                await wait_for_menu_titled(pilot, "Settings")
                await pilot.press("a")  # ANSI color blocks
                await wait_for_menu_titled(pilot, "Bin Inventory")
                await pilot.press("x")
                await wait_for_exit(app)
            assert save_mock.called
        assert cfg["image_mode"] == "ansi"
        # Live-updated without needing an app restart — bi_python re-read
        # cfg["image_mode"] fresh on every image view; TextualRenderer
        # caches it, so app.py's _settings_menu must update it live to match.
        assert app.renderer.image_mode == "ansi"
        assert app.renderer.image_capability == ImageCapability.ANSI_PIXELS

    run(_body)


def test_settings_back_makes_no_change():
    async def _body():
        client = MagicMock()
        client.get_item_count.return_value = {"number": 0}
        cfg = make_cfg(image_mode="ascii")
        app = make_app(client=client, cfg=cfg)
        with patched_config_save() as save_mock:
            async with app.run_test() as pilot:
                await wait_for_menu_titled(pilot, "Bin Inventory")
                await pilot.press("t")
                await wait_for_menu_titled(pilot, "Settings")
                await pilot.press("b")
                await wait_for_menu_titled(pilot, "Bin Inventory")
                await pilot.press("x")
                await wait_for_exit(app)
            save_mock.assert_not_called()
        assert cfg["image_mode"] == "ascii"

    run(_body)
