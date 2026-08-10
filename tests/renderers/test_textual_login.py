from unittest.mock import MagicMock

from bi_terminal.core.errors import APIError
from bi_terminal.renderers.textual.screens import FormScreen

from ._helpers import (
    fill_form_fields,
    make_app,
    make_cfg,
    patched_config_save,
    run,
    wait_for_exit,
    wait_for_menu_titled,
    wait_for_screen_type,
)


def _cfg_without_token():
    cfg = make_cfg()
    cfg.pop("token", None)
    cfg.pop("userId", None)
    return cfg


def test_no_token_shows_login_choice_then_exit():
    async def _body():
        client = MagicMock()
        app = make_app(client=client, cfg=_cfg_without_token())
        with patched_config_save() as save_mock:
            async with app.run_test() as pilot:
                await wait_for_menu_titled(pilot, "Binventory")
                await pilot.press("x")
                await wait_for_exit(app)
            save_mock.assert_not_called()  # never logged in, nothing to persist
        assert not client.login.called
        assert not client.signup.called

    run(_body)


def test_login_success_reaches_main_menu_and_saves_config():
    async def _body():
        client = MagicMock()
        client.login.return_value = {"token": "tok123", "userId": "u9", "email": "a@b.com"}
        client.get_item_count.return_value = {"number": 2}
        cfg = _cfg_without_token()
        app = make_app(client=client, cfg=cfg)
        with patched_config_save() as save_mock:
            async with app.run_test() as pilot:
                await wait_for_menu_titled(pilot, "Binventory")
                await pilot.press("l")
                screen = await wait_for_screen_type(pilot, FormScreen)
                fill_form_fields(screen, {"email": "a@b.com", "password": "hunter2"})
                await pilot.press("ctrl+s")
                await wait_for_menu_titled(pilot, "Bin Inventory")
                await pilot.press("x")
                await wait_for_exit(app)
            assert save_mock.called
        client.login.assert_called_once_with("a@b.com", "hunter2")
        assert cfg["token"] == "tok123"
        assert cfg["userId"] == "u9"
        assert cfg["email"] == "a@b.com"
        assert client.token == "tok123"

    run(_body)


def test_login_enter_in_password_field_submits_without_ctrl_s():
    """Real, live-reported bug (2026-08-10): "bi-terminal-textual requires
    you to press CTRL-S to login. Pressing ENTER after typing in your
    password should log you in." Deliberately does NOT press ctrl+s at
    all -- the whole point is proving Enter alone, in the form's last
    field, is now sufficient."""

    async def _body():
        client = MagicMock()
        client.login.return_value = {"token": "tok123", "userId": "u9", "email": "a@b.com"}
        client.get_item_count.return_value = {"number": 2}
        cfg = _cfg_without_token()
        app = make_app(client=client, cfg=cfg)
        with patched_config_save():
            async with app.run_test() as pilot:
                await wait_for_menu_titled(pilot, "Binventory")
                await pilot.press("l")
                screen = await wait_for_screen_type(pilot, FormScreen)
                fill_form_fields(screen, {"email": "a@b.com", "password": "hunter2"})
                screen.query_one("#password").focus()
                await pilot.pause()
                await pilot.press("enter")
                await wait_for_menu_titled(pilot, "Bin Inventory")
                await pilot.press("x")
                await wait_for_exit(app)
        client.login.assert_called_once_with("a@b.com", "hunter2")

    run(_body)


def test_login_failure_returns_to_login_choice_not_a_crash():
    async def _body():
        client = MagicMock()
        client.login.side_effect = APIError("Invalid credentials", status_code=401)
        app = make_app(client=client, cfg=_cfg_without_token())
        with patched_config_save():
            async with app.run_test() as pilot:
                await wait_for_menu_titled(pilot, "Binventory")
                await pilot.press("l")
                screen = await wait_for_screen_type(pilot, FormScreen)
                fill_form_fields(screen, {"email": "a@b.com", "password": "wrong"})
                await pilot.press("ctrl+s")
                # Failed login -> back to the Login/Signup/Exit choice, not a crash
                await wait_for_menu_titled(pilot, "Binventory")
                await pilot.press("x")
                await wait_for_exit(app)

    run(_body)


def test_signup_success_reaches_main_menu():
    async def _body():
        client = MagicMock()
        client.signup.return_value = {"token": "tok456", "userId": "u10", "email": "new@b.com"}
        client.get_item_count.return_value = {"number": 0}
        cfg = _cfg_without_token()
        app = make_app(client=client, cfg=cfg)
        with patched_config_save():
            async with app.run_test() as pilot:
                await wait_for_menu_titled(pilot, "Binventory")
                await pilot.press("s")
                screen = await wait_for_screen_type(pilot, FormScreen)
                fill_form_fields(
                    screen, {"name": "New User", "email": "new@b.com", "password": "hunter22"}
                )
                await pilot.press("ctrl+s")
                await wait_for_menu_titled(pilot, "Bin Inventory")
                await pilot.press("x")
                await wait_for_exit(app)
        client.signup.assert_called_once()
        assert cfg["token"] == "tok456"

    run(_body)


def test_logout_returns_to_login_choice_and_clears_token():
    async def _body():
        client = MagicMock()
        client.get_item_count.return_value = {"number": 0}
        cfg = make_cfg()  # has a token
        app = make_app(client=client, cfg=cfg)
        with patched_config_save():
            async with app.run_test() as pilot:
                await wait_for_menu_titled(pilot, "Bin Inventory")
                await pilot.press("l")  # Logout shortcut on the main menu
                await wait_for_menu_titled(pilot, "Binventory")
                assert "token" not in cfg
                assert client.token is None
                await pilot.press("x")
                await wait_for_exit(app)

    run(_body)
