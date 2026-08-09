"""AppDriver tests using a minimal scripted fake Renderer — no real I/O at
all, proving the shared flow-orchestration logic once, fast and decoupled
from any concrete renderer's I/O quirks. The Textual renderer's 92-test
suite (tests/renderers/test_textual_*.py) already exercises this exact same
driver code end-to-end through real screens; this file targets the driver's
own control-flow behavior directly instead.

Critical methodology note, same as the Textual suite: any test whose code
path touches core.config (login, logout, settings, profile-email-change)
patches core.config.save so it can never touch the real
~/.binventory/config.json.
"""

from unittest.mock import MagicMock, patch

from bi_terminal.core import config as config_module
from bi_terminal.core.errors import APIError, ImageFileNotFoundError
from bi_terminal.core.flow import GlobalNavigate
from bi_terminal.driver import AppDriver
from bi_terminal.renderers.base import ImageCapability
from bi_terminal.specs.base import CANCELLED


class ScriptedRenderer:
    """Every show_* call pops the next value off `script`, in call order.
    notify/show_image don't consume the script — they just record."""

    image_capability = ImageCapability.NONE

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def _next(self, kind, spec):
        self.calls.append((kind, spec))
        assert self.script, f"ScriptedRenderer ran out of script at a {kind} call"
        return self.script.pop(0)

    def show_action_menu(self, spec):
        return self._next("action_menu", spec)

    def show_list_picker(self, spec):
        return self._next("list_picker", spec)

    def show_form(self, spec):
        return self._next("form", spec)

    def show_confirm(self, spec):
        return self._next("confirm", spec)

    def show_text_prompt(self, spec):
        return self._next("text_prompt", spec)

    def show_image(self, urls, start_index=0):
        self.calls.append(("image", urls))

    def notify(self, message, severity="information"):
        self.calls.append(("notify", severity, message))

    def error_notifies(self):
        return [c for c in self.calls if c[0] == "notify" and c[1] == "error"]


def _cfg(**overrides):
    cfg = {"base_url": "https://example.invalid/api", "image_mode": "none"}
    cfg.update(overrides)
    return cfg


def test_login_success_saves_config_and_reaches_main_dispatch():
    client = MagicMock()
    client.login.return_value = {"token": "tok", "userId": "u9", "email": "a@b.com"}
    client.get_item_count.return_value = {"number": 0}
    cfg = _cfg()
    renderer = ScriptedRenderer(
        script=[
            "login",  # login_choice_spec action menu
            {"email": "a@b.com", "password": "pw"},  # login_form_spec
            "exit",  # main_menu_spec action menu
        ]
    )
    exits = []
    driver = AppDriver(cfg, client, renderer, on_exit=lambda: exits.append(True))
    with patch.object(config_module, "save") as save_mock:
        driver.run()
        assert save_mock.called
    client.login.assert_called_once_with("a@b.com", "pw")
    assert cfg["token"] == "tok"
    assert cfg["userId"] == "u9"
    assert exits == [True]


def test_login_failure_loops_back_to_login_choice():
    client = MagicMock()
    client.login.side_effect = APIError("bad creds", status_code=401)
    cfg = _cfg()
    renderer = ScriptedRenderer(
        script=[
            "login",
            {"email": "a@b.com", "password": "wrong"},
            "exit",  # back at login_choice after the failed attempt
        ]
    )
    exits = []
    driver = AppDriver(cfg, client, renderer, on_exit=lambda: exits.append(True))
    with patch.object(config_module, "save"):
        driver.run()
    assert exits == [True]
    assert "token" not in cfg


def test_bins_menu_404_is_empty_not_an_error():
    client = MagicMock()
    client.get_item_count.return_value = {"number": 0}
    client.get_bins_by_user.side_effect = APIError("not found", status_code=404)
    cfg = _cfg(token="t", userId="u1", email="a@b.com")
    renderer = ScriptedRenderer(script=["bins", CANCELLED, "exit"])
    exits = []
    driver = AppDriver(cfg, client, renderer, on_exit=lambda: exits.append(True))
    with patch.object(config_module, "save"):
        driver.run()
    assert exits == [True]
    assert renderer.error_notifies() == []  # the 404 must NOT surface as an error


def test_bins_menu_non_404_error_does_surface():
    client = MagicMock()
    client.get_item_count.return_value = {"number": 0}
    client.get_bins_by_user.side_effect = APIError("server error", status_code=500)
    cfg = _cfg(token="t", userId="u1", email="a@b.com")
    renderer = ScriptedRenderer(script=["bins", "exit"])  # no list_picker call -- bins_menu returns early
    exits = []
    driver = AppDriver(cfg, client, renderer, on_exit=lambda: exits.append(True))
    with patch.object(config_module, "save"):
        driver.run()
    assert exits == [True]
    assert len(renderer.error_notifies()) == 1


def test_create_bin_image_not_found_retry_then_success():
    client = MagicMock()
    client.get_item_count.return_value = {"number": 0}
    client.create_bin.side_effect = [
        ImageFileNotFoundError("/bad/path.png"),
        {"bin": {"id": "b1", "binName": "Shelf X"}},
    ]
    cfg = _cfg(token="t", userId="u1", email="a@b.com")
    renderer = ScriptedRenderer(
        script=[
            "new_bin",  # main menu
            {
                "bin_name": "Shelf X",
                "description": "",
                "location": "",
                "bin_type": "",
                "public": False,
                "sw_emails": "",
                "image_path": "/bad/path.png",
            },
            "/good/path.png",  # retry prompt
            "exit",  # main menu again
        ]
    )
    exits = []
    driver = AppDriver(cfg, client, renderer, on_exit=lambda: exits.append(True))
    with patch.object(config_module, "save"):
        driver.run()
    assert exits == [True]
    assert client.create_bin.call_count == 2
    assert client.create_bin.call_args.kwargs["image_path"] == "/good/path.png"
    assert renderer.error_notifies() == []


def test_create_bin_image_not_found_gives_up_on_cancel():
    client = MagicMock()
    client.get_item_count.return_value = {"number": 0}
    client.create_bin.side_effect = ImageFileNotFoundError("/bad/path.png")
    cfg = _cfg(token="t", userId="u1", email="a@b.com")
    renderer = ScriptedRenderer(
        script=[
            "new_bin",
            {
                "bin_name": "Shelf X",
                "description": "",
                "location": "",
                "bin_type": "",
                "public": False,
                "sw_emails": "",
                "image_path": "/bad/path.png",
            },
            CANCELLED,  # user gives up the retry prompt
            "exit",
        ]
    )
    exits = []
    driver = AppDriver(cfg, client, renderer, on_exit=lambda: exits.append(True))
    with patch.object(config_module, "save"):
        driver.run()
    assert exits == [True]
    assert client.create_bin.call_count == 1  # no retry attempted
    assert len(renderer.error_notifies()) == 1


def test_global_navigate_from_main_menu_routes_to_bins_and_calls_hook():
    client = MagicMock()
    client.get_item_count.return_value = {"number": 0}
    client.get_bins_by_user.return_value = {"bins": []}
    cfg = _cfg(token="t", userId="u1", email="a@b.com")
    renderer = ScriptedRenderer(script=[GlobalNavigate("bins"), CANCELLED, "exit"])
    exits = []
    nav_unwinds = []
    driver = AppDriver(
        cfg,
        client,
        renderer,
        on_global_navigate=lambda: nav_unwinds.append(True),
        on_exit=lambda: exits.append(True),
    )
    with patch.object(config_module, "save"):
        driver.run()
    assert nav_unwinds == [True]
    assert exits == [True]
    # proves the GlobalNavigate value genuinely routed dispatch to "bins",
    # not just that it didn't crash -- get_bins_by_user was actually called
    client.get_bins_by_user.assert_called_once()


def test_settings_menu_never_touches_renderer_internals():
    """The coupling fix from the driver-extraction refactor: _settings_menu
    only ever writes cfg["image_mode"] and calls renderer.notify — it must
    never reach into renderer-specific attributes, which the shared driver
    can't know about anyway."""
    client = MagicMock()
    client.get_item_count.return_value = {"number": 0}
    cfg = _cfg(token="t", userId="u1", email="a@b.com", image_mode="none")
    renderer = ScriptedRenderer(script=["settings", "ansi", "exit"])
    exits = []
    driver = AppDriver(cfg, client, renderer, on_exit=lambda: exits.append(True))
    with patch.object(config_module, "save") as save_mock:
        driver.run()
        assert save_mock.called
    assert exits == [True]
    assert cfg["image_mode"] == "ansi"
    assert any(c[0] == "notify" and "ansi" in c[2].lower() for c in renderer.calls)
