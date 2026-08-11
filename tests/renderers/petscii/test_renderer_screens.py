import io as pyio
import os
from unittest.mock import patch

from bi_terminal.core.flow import GlobalNavigate
from bi_terminal.renderers.base import ImageCapability
from bi_terminal.renderers.petscii import petscii_codes as pc
from bi_terminal.renderers.petscii.io import PetsciiIO
from bi_terminal.renderers.petscii.renderer import PetsciiRenderer
from bi_terminal.specs.base import CANCELLED, EMPTY_SUBMIT
from bi_terminal.specs.fields import (
    ActionItem,
    ActionMenuSpec,
    Choice,
    ComboFilterSelectField,
    ConfirmSpec,
    FormSpec,
    ImageManagerField,
    ImagePathField,
    ListPickerSpec,
    MultiImagePathField,
    SwitchField,
    TextField,
    TextPromptSpec,
)

RET = pc.RETURN


def _make(write_bytes: bytes):
    r_fd, w_fd = os.pipe()
    os.write(w_fd, write_bytes)
    out = pyio.BytesIO()
    io_obj = PetsciiIO(r_fd, out)
    return PetsciiRenderer(io_obj), out, (r_fd, w_fd)


def _close(fds):
    for fd in fds:
        try:
            os.close(fd)
        except OSError:
            pass


def test_image_capability_is_petscii_graphics():
    assert PetsciiRenderer.image_capability == ImageCapability.PETSCII_GRAPHICS


def test_construction_sends_lowercase_switch_before_anything_else():
    r, out, fds = _make(b"")
    _close(fds)
    assert out.getvalue() == pc.SWITCH_TO_LOWERCASE


# ── show_action_menu ─────────────────────────────────────────────────────


def test_action_menu_shortcut_match():
    r, out, fds = _make(b"b")
    spec = ActionMenuSpec(
        title="Main", items=[ActionItem("My Bins", "b", "bins")], nav_enabled=False
    )
    result = r.show_action_menu(spec)
    _close(fds)
    assert result == "bins"


def test_action_menu_escape_returns_cancelled():
    r, out, fds = _make(bytes([0x1B]))
    spec = ActionMenuSpec(title="Main", items=[ActionItem("Exit", "x", "exit")], nav_enabled=False)
    result = r.show_action_menu(spec)
    _close(fds)
    assert result is CANCELLED


def test_action_menu_nav_digit_returns_global_navigate():
    r, out, fds = _make(b"2")
    spec = ActionMenuSpec(title="Main", items=[ActionItem("Exit", "x", "exit")], nav_enabled=True)
    result = r.show_action_menu(spec)
    _close(fds)
    assert isinstance(result, GlobalNavigate)
    assert result.dest == "bins"


def test_action_menu_uses_cyan_and_yellow_control_bytes():
    r, out, fds = _make(b"x")
    spec = ActionMenuSpec(title="Main", items=[ActionItem("Exit", "x", "exit")], nav_enabled=False)
    r.show_action_menu(spec)
    val = out.getvalue()
    _close(fds)
    assert pc.CYAN in val
    assert pc.YELLOW in val


def test_action_menu_em_dash_in_title_is_sanitized():
    r, out, fds = _make(b"x")
    spec = ActionMenuSpec(
        title="Bin Inventory — 5 items", items=[ActionItem("Exit", "x", "exit")], nav_enabled=False
    )
    r.show_action_menu(spec)
    val = out.getvalue()
    _close(fds)
    assert "—".encode("utf-8") not in val
    assert b"-" in val


# ── show_list_picker ─────────────────────────────────────────────────────


def test_list_picker_enter_selects_first_highlighted():
    r, out, fds = _make(RET)
    spec = ListPickerSpec(title="Items", choices=[Choice("Widget", "w1"), Choice("Gadget", "g1")])
    result = r.show_list_picker(spec)
    _close(fds)
    assert result == "w1"


def test_list_picker_uses_reverse_video_for_highlight_not_color():
    r, out, fds = _make(RET)
    spec = ListPickerSpec(title="Items", choices=[Choice("Widget", "w1")])
    r.show_list_picker(spec)
    val = out.getvalue()
    _close(fds)
    assert pc.REVERSE_ON in val
    assert pc.REVERSE_OFF in val


def test_list_picker_down_arrow_moves_highlight():
    r, out, fds = _make(bytes([17]) + RET)
    spec = ListPickerSpec(title="Items", choices=[Choice("Widget", "w1"), Choice("Gadget", "g1")])
    result = r.show_list_picker(spec)
    _close(fds)
    assert result == "g1"


def test_list_picker_filter_narrows_choices():
    r, out, fds = _make(b"gad" + RET)
    spec = ListPickerSpec(title="Items", choices=[Choice("Widget", "w1"), Choice("Gadget", "g1")])
    result = r.show_list_picker(spec)
    _close(fds)
    assert result == "g1"


def test_list_picker_escape_cancels():
    r, out, fds = _make(bytes([0x1B]))
    spec = ListPickerSpec(title="Items", choices=[Choice("Widget", "w1")])
    result = r.show_list_picker(spec)
    _close(fds)
    assert result is CANCELLED


def test_list_picker_long_names_are_truncated_to_fit_40_columns():
    long_name = "A" * 60
    r, out, fds = _make(RET)
    spec = ListPickerSpec(title="Items", choices=[Choice(long_name, "x1")])
    r.show_list_picker(spec)
    val = out.getvalue()
    _close(fds)
    assert long_name.encode("ascii") not in val  # never emitted un-truncated


def test_list_picker_scroll_window_for_long_lists_is_smaller_than_ansi():
    choices = [Choice(f"Item {i}", i) for i in range(20)]
    r, out, fds = _make(RET)
    spec = ListPickerSpec(title="Items", choices=choices)
    result = r.show_list_picker(spec)
    val = out.getvalue()
    _close(fds)
    assert result == 0
    assert b"OF 20" in val  # case swapped -- see sanitize.py


# ── show_form ────────────────────────────────────────────────────────────


def test_form_collects_multiple_field_types():
    r, out, fds = _make(b"Shelf B" + RET + b"y" + RET)
    spec = FormSpec(
        title="New Bin",
        fields=[TextField("bin_name", "Name"), SwitchField("public", "Public", default=False)],
    )
    result = r.show_form(spec)
    _close(fds)
    assert result == {"bin_name": "Shelf B", "public": True}


def test_form_escape_on_any_field_cancels_whole_form():
    r, out, fds = _make(b"typed" + bytes([0x1B]))
    spec = FormSpec(title="F", fields=[TextField("a", "A"), TextField("b", "B")])
    result = r.show_form(spec)
    _close(fds)
    assert result is CANCELLED


def test_form_validator_reprompts_only_the_failing_field():
    def non_blank(v):
        return None if str(v or "").strip() else "Required"

    r, out, fds = _make(RET + b"d@example.com" + RET + b"ok" + RET)
    spec = FormSpec(
        title="F",
        fields=[
            TextField("name", "Name", required=True, validator=non_blank),
            TextField("email", "Email", required=True, validator=non_blank),
        ],
    )
    result = r.show_form(spec)
    _close(fds)
    assert result == {"name": "ok", "email": "d@example.com"}


def test_form_combo_filter_select_field_reuses_list_picker():
    r, out, fds = _make(RET)
    spec = FormSpec(
        title="F",
        fields=[
            ComboFilterSelectField(
                "bin_id", "Bin", choices=[Choice("Shelf A", "b1"), Choice("Shelf B", "b2")]
            )
        ],
    )
    result = r.show_form(spec)
    _close(fds)
    assert result == {"bin_id": "b1"}


def test_form_combo_filter_select_field_preselects_current_value():
    """Regression test for a real bug (reported live, 2026-08-10) — see
    ansi/test_renderer_screens.py's identical test for the full story."""
    r, out, fds = _make(RET)
    spec = FormSpec(
        title="F",
        fields=[
            ComboFilterSelectField(
                "bin_id",
                "Bin",
                choices=[Choice("Shelf A", "b1"), Choice("Shelf B", "b2")],
                default_value="b2",
            )
        ],
    )
    result = r.show_form(spec)
    _close(fds)
    assert result == {"bin_id": "b2"}


def test_list_picker_initial_value_preselects_matching_choice():
    r, out, fds = _make(RET)
    spec = ListPickerSpec(
        title="Items",
        choices=[Choice("Widget", "w1"), Choice("Gadget", "g1"), Choice("Gizmo", "z1")],
        initial_value="g1",
    )
    result = r.show_list_picker(spec)
    _close(fds)
    assert result == "g1"


def test_form_image_manager_field_passes_through_unchanged():
    r, out, fds = _make(b"")
    spec = FormSpec(
        title="F", fields=[ImageManagerField("existing_images", "Images", images=["a.png"])]
    )
    result = r.show_form(spec)
    _close(fds)
    assert result == {"existing_images": ["a.png"]}


def test_form_multi_image_path_field_splits_on_commas():
    r, out, fds = _make(b"a.png, b.png ," + RET)
    spec = FormSpec(title="F", fields=[MultiImagePathField("new_image_paths", "New Images")])
    result = r.show_form(spec)
    _close(fds)
    assert result == {"new_image_paths": ["a.png", "b.png"]}


def test_form_image_path_field_blank_becomes_none():
    r, out, fds = _make(RET)
    spec = FormSpec(title="F", fields=[ImagePathField("image_path", "Image")])
    result = r.show_form(spec)
    _close(fds)
    assert result == {"image_path": None}


# ── show_confirm ─────────────────────────────────────────────────────────


def test_confirm_yes():
    r, out, fds = _make(b"y")
    result = r.show_confirm(ConfirmSpec(prompt="Delete?"))
    _close(fds)
    assert result is True


def test_confirm_no():
    r, out, fds = _make(b"n")
    result = r.show_confirm(ConfirmSpec(prompt="Delete?"))
    _close(fds)
    assert result is False


def test_confirm_escape_resolves_to_default():
    r, out, fds = _make(bytes([0x1B]))
    result = r.show_confirm(ConfirmSpec(prompt="Delete?", default=False))
    _close(fds)
    assert result is False


# ── show_text_prompt ─────────────────────────────────────────────────────


def test_text_prompt_basic():
    r, out, fds = _make(b"some/path.png" + RET)
    result = r.show_text_prompt(TextPromptSpec(title="Retry", prompt="Path?"))
    _close(fds)
    assert result == "some/path.png"


def test_text_prompt_distinguishes_empty_submit_from_cancel():
    r, out, fds = _make(RET)
    result = r.show_text_prompt(
        TextPromptSpec(title="Search", prompt="Query?", distinguish_empty_submit=True)
    )
    _close(fds)
    assert result is EMPTY_SUBMIT


# ── show_image / notify ──────────────────────────────────────────────────


def test_show_image_renders_real_petscii_art_bytes():
    """Real image support, shipped 2026-08-11 in response to a direct
    question ("SyncTERM/Synchronet document supporting ANSI/PETSCII
    graphics, why doesn't this door do it") -- the honest answer was "not
    impossible, just not built yet," so it got built. Mocks
    image_to_petscii_bytes (a real network call otherwise) to isolate
    show_image's own screen-flow logic from the actual PIL/requests
    conversion, which petscii_art.py's own tests cover directly."""
    fake_art = pc.REVERSE_ON + pc.RED + b"  " + pc.RETURN + pc.REVERSE_OFF
    with patch(
        "bi_terminal.renderers.petscii.renderer.image_to_petscii_bytes", return_value=fake_art
    ):
        r, out, fds = _make(b"x")  # any key closes a single-image view
        result = r.show_image(["https://example.com/x.png"])
        val = out.getvalue()
        _close(fds)
    assert result is None
    assert fake_art in val
    assert b"press any key" in val.lower()


def test_show_image_load_failure_notifies_not_a_silent_gap():
    """image_to_petscii_bytes returning None (bad URL, network error,
    unsupported format -- see its own docstring) must still tell the user
    something, matching the same "never leave a silent gap" principle the
    original not-yet-supported message was built around."""
    with patch(
        "bi_terminal.renderers.petscii.renderer.image_to_petscii_bytes", return_value=None
    ):
        r, out, fds = _make(b"x")
        result = r.show_image(["https://example.com/broken.png"])
        val = out.getvalue()
        _close(fds)
    assert result is None
    assert b"could not load" in val.lower()


def test_show_image_no_urls_notifies_and_returns_immediately():
    r, out, fds = _make(b"")
    result = r.show_image([])
    val = out.getvalue()
    _close(fds)
    assert result is None
    assert b"no images" in val.lower()


def test_show_image_left_right_cycles_between_multiple_images():
    """Only reliable now that a real, live-reported cursor-key bug was
    root-caused and fixed the same day (see io.py's PetsciiKeyReader
    docstring) -- left/right cycling genuinely depends on that fix."""
    calls = []

    def _fake(url):
        calls.append(url)
        return pc.WHITE + url[-1].encode("ascii") + pc.RETURN  # last char identifies which image

    with patch("bi_terminal.renderers.petscii.renderer.image_to_petscii_bytes", side_effect=_fake):
        # right (0x06, Synchronet-translated -- see io.py) -> image B,
        # right again -> wraps to image A, escape closes
        r, out, fds = _make(bytes([6, 6, 0x1B]))
        result = r.show_image(["https://example.com/a.png", "https://example.com/b.png"])
        val = out.getvalue()
        _close(fds)
    assert result is None
    assert calls == [
        "https://example.com/a.png",
        "https://example.com/b.png",
        "https://example.com/a.png",
    ]
    assert b"l/r SWITCH" in val  # case swapped -- see sanitize.py


def test_notify_error_uses_red_control_byte():
    r, out, fds = _make(b"")
    r.notify("Something broke", severity="error")
    val = out.getvalue()
    _close(fds)
    assert pc.RED in val
    assert b"sOMETHING BROKE" in val  # case swapped -- see sanitize.py


def test_notify_warning_uses_yellow_control_byte():
    r, out, fds = _make(b"")
    r.notify("Heads up", severity="warning")
    val = out.getvalue()
    _close(fds)
    assert pc.YELLOW in val
