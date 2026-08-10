import io as pyio
import os

from bi_terminal.core.flow import GlobalNavigate
from bi_terminal.renderers.ansi.io import AnsiIO
from bi_terminal.renderers.ansi.renderer import AnsiRenderer
from bi_terminal.renderers.base import ImageCapability
from bi_terminal.specs.base import CANCELLED, EMPTY_SUBMIT
from bi_terminal.specs.fields import (
    ActionItem,
    ActionMenuSpec,
    Choice,
    ComboFilterSelectField,
    ConfirmSpec,
    FormSpec,
    ImageManagerField,
    ListPickerSpec,
    SwitchField,
    TextField,
    TextPromptSpec,
)


def _make(write_bytes: bytes):
    r_fd, w_fd = os.pipe()
    os.write(w_fd, write_bytes)
    out = pyio.StringIO()
    io_obj = AnsiIO(r_fd, out)
    return AnsiRenderer(io_obj), out, (r_fd, w_fd)


def _close(fds):
    for fd in fds:
        try:
            os.close(fd)
        except OSError:
            pass


def test_image_capability_is_fixed_at_none():
    assert AnsiRenderer.image_capability == ImageCapability.NONE


def test_header_applies_navy_background_before_clearing():
    """Real bug, fixed 2026-08-10: NAVY_BG was defined in ansi_codes.py but
    never actually emitted anywhere, so the screen never showed the
    intended navy background at all. BASE_SGR must be written BEFORE
    CLEAR_SCREEN -- a real terminal fills the erased area using whatever
    background is active at the moment of the erase."""
    from bi_terminal.renderers.ansi.ansi_codes import BASE_SGR, CLEAR_SCREEN

    r, out, fds = _make(b"x")
    r.show_action_menu(
        ActionMenuSpec(title="Main", items=[ActionItem("Exit", "x", "exit")], nav_enabled=False)
    )
    val = out.getvalue()
    _close(fds)
    assert val.index(BASE_SGR) < val.index(CLEAR_SCREEN)


# ── show_action_menu ─────────────────────────────────────────────────────


def test_action_menu_shortcut_match():
    r, out, fds = _make(b"b")
    spec = ActionMenuSpec(
        title="Main",
        items=[ActionItem("My Bins", "b", "bins"), ActionItem("Exit", "x", "exit")],
        nav_enabled=False,
    )
    result = r.show_action_menu(spec)
    _close(fds)
    assert result == "bins"
    assert "[B]" in out.getvalue() and "My Bins" in out.getvalue()


def test_action_menu_shortcut_case_insensitive():
    r, out, fds = _make(b"B")
    spec = ActionMenuSpec(title="Main", items=[ActionItem("My Bins", "b", "bins")], nav_enabled=False)
    result = r.show_action_menu(spec)
    _close(fds)
    assert result == "bins"


def test_action_menu_escape_returns_cancelled():
    r, out, fds = _make(b"\x1b")
    spec = ActionMenuSpec(title="Main", items=[ActionItem("Exit", "x", "exit")], nav_enabled=False)
    result = r.show_action_menu(spec)
    _close(fds)
    assert result is CANCELLED


def test_action_menu_nav_digit_returns_global_navigate_when_enabled():
    r, out, fds = _make(b"2")
    spec = ActionMenuSpec(title="Main", items=[ActionItem("Exit", "x", "exit")], nav_enabled=True)
    result = r.show_action_menu(spec)
    _close(fds)
    assert isinstance(result, GlobalNavigate)
    assert result.dest == "bins"


def test_action_menu_nav_digit_is_a_plain_noop_when_disabled():
    r, out, fds = _make(b"2x")
    spec = ActionMenuSpec(title="Main", items=[ActionItem("Exit", "x", "exit")], nav_enabled=False)
    result = r.show_action_menu(spec)
    _close(fds)
    assert result == "exit"  # the '2' did nothing, 'x' was what matched


def test_action_menu_separator_does_not_crash_and_is_not_matchable():
    r, out, fds = _make(b"x")
    spec = ActionMenuSpec(
        title="Main",
        items=[ActionItem(separator=True), ActionItem("Exit", "x", "exit")],
        nav_enabled=False,
    )
    result = r.show_action_menu(spec)
    _close(fds)
    assert result == "exit"


def test_action_menu_em_dash_in_title_is_sanitized():
    """Real bug fixed 2026-08-10 -- see ansi/io.py's write()/sanitize.py.
    Mirrors the equivalent PETSCII/ATASCII regression tests."""
    r, out, fds = _make(b"x")
    spec = ActionMenuSpec(
        title="Bin Inventory — 5 items", items=[ActionItem("Exit", "x", "exit")], nav_enabled=False
    )
    r.show_action_menu(spec)
    val = out.getvalue()
    _close(fds)
    assert "—" not in val
    assert "-" in val


def test_action_menu_detail_prompt_lines_are_rendered():
    r, out, fds = _make(b"x")
    spec = ActionMenuSpec(
        title="Bin: Shelf A",
        prompt="Name: Shelf A\nLocation: Workshop",
        items=[ActionItem("Back", "x", "back")],
    )
    r.show_action_menu(spec)
    _close(fds)
    assert "Shelf A" in out.getvalue()
    assert "Workshop" in out.getvalue()


# ── show_list_picker ─────────────────────────────────────────────────────


def test_list_picker_enter_selects_first_highlighted():
    r, out, fds = _make(b"\r")
    spec = ListPickerSpec(title="Items", choices=[Choice("Widget", "w1"), Choice("Gadget", "g1")])
    result = r.show_list_picker(spec)
    _close(fds)
    assert result == "w1"


def test_list_picker_down_arrow_moves_highlight():
    r, out, fds = _make(b"\x1b[B\r")  # down, enter
    spec = ListPickerSpec(title="Items", choices=[Choice("Widget", "w1"), Choice("Gadget", "g1")])
    result = r.show_list_picker(spec)
    _close(fds)
    assert result == "g1"


def test_list_picker_wraps_around():
    r, out, fds = _make(b"\x1b[A\r")  # up from index 0 -> wraps to last
    spec = ListPickerSpec(title="Items", choices=[Choice("Widget", "w1"), Choice("Gadget", "g1")])
    result = r.show_list_picker(spec)
    _close(fds)
    assert result == "g1"


def test_list_picker_filter_narrows_choices():
    r, out, fds = _make(b"gad\r")
    spec = ListPickerSpec(title="Items", choices=[Choice("Widget", "w1"), Choice("Gadget", "g1")])
    result = r.show_list_picker(spec)
    _close(fds)
    assert result == "g1"


def test_list_picker_backspace_widens_filter_back():
    r, out, fds = _make(b"gadX\x7f\r")  # "gadX" matches nothing, backspace -> "gad" matches Gadget
    spec = ListPickerSpec(title="Items", choices=[Choice("Widget", "w1"), Choice("Gadget", "g1")])
    result = r.show_list_picker(spec)
    _close(fds)
    assert result == "g1"


def test_list_picker_enter_on_empty_matches_does_nothing_then_escape_cancels():
    r, out, fds = _make(b"zzz\r\x1b")
    spec = ListPickerSpec(title="Items", choices=[Choice("Widget", "w1")])
    result = r.show_list_picker(spec)
    _close(fds)
    assert result is CANCELLED


def test_list_picker_escape_cancels():
    r, out, fds = _make(b"\x1b")
    spec = ListPickerSpec(title="Items", choices=[Choice("Widget", "w1")])
    result = r.show_list_picker(spec)
    _close(fds)
    assert result is CANCELLED


def test_list_picker_extra_lines_rendered():
    r, out, fds = _make(b"\x1b")
    spec = ListPickerSpec(title="Items", choices=[], extra_lines=["You have no items yet."])
    r.show_list_picker(spec)
    _close(fds)
    assert "You have no items yet." in out.getvalue()


def test_list_picker_scroll_window_for_long_lists():
    choices = [Choice(f"Item {i}", i) for i in range(30)]
    r, out, fds = _make(b"\r")
    spec = ListPickerSpec(title="Items", choices=choices)
    result = r.show_list_picker(spec)
    _close(fds)
    assert result == 0
    assert "showing" in out.getvalue()


# ── show_form ────────────────────────────────────────────────────────────


def test_form_collects_multiple_field_types():
    r, out, fds = _make(b"Shelf B\ry\r")  # text field, then Y for switch
    spec = FormSpec(
        title="New Bin",
        fields=[TextField("bin_name", "Name"), SwitchField("public", "Public", default=False)],
    )
    result = r.show_form(spec)
    _close(fds)
    assert result == {"bin_name": "Shelf B", "public": True}


def test_form_switch_default_on_bare_enter():
    r, out, fds = _make(b"\r")
    spec = FormSpec(title="F", fields=[SwitchField("public", "Public", default=True)])
    result = r.show_form(spec)
    _close(fds)
    assert result == {"public": True}


def test_form_escape_on_any_field_cancels_whole_form():
    r, out, fds = _make(b"typed\x1b")
    spec = FormSpec(
        title="F",
        fields=[TextField("a", "A"), TextField("b", "B")],
    )
    result = r.show_form(spec)
    _close(fds)
    assert result is CANCELLED


def test_form_validator_reprompts_only_the_failing_field():
    def non_blank(v):
        return None if str(v or "").strip() else "Required"

    # All fields are collected up front (name blank, email filled) before
    # any validation runs, matching the Textual FormScreen's contract; only
    # THEN does validation find name blank and re-prompt just that field.
    r, out, fds = _make(b"\rd@example.com\rok\r")
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
    r, out, fds = _make(b"\r")
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
    """Regression test for a real bug (reported live, 2026-08-10): editing
    an item whose Bin is NOT the first choice used to always highlight the
    first bin regardless -- pressing Enter without deliberately re-picking
    would silently reassign the item to the wrong bin. default_value="b2"
    (the second of two choices) must be highlighted already, so a bare
    Enter keeps the item on its actual current bin."""
    r, out, fds = _make(b"\r")
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
    r, out, fds = _make(b"\r")  # bare Enter, no navigation at all
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
        title="F",
        fields=[ImageManagerField("existing_images", "Images", images=["a.png", "b.png"])],
    )
    result = r.show_form(spec)
    _close(fds)
    assert result == {"existing_images": ["a.png", "b.png"]}
    assert "not editable" in out.getvalue()


def test_form_multi_image_path_field_splits_on_commas():
    from bi_terminal.specs.fields import MultiImagePathField

    r, out, fds = _make(b"a.png, b.png ,\r")
    spec = FormSpec(title="F", fields=[MultiImagePathField("new_image_paths", "New Images")])
    result = r.show_form(spec)
    _close(fds)
    assert result == {"new_image_paths": ["a.png", "b.png"]}


def test_form_image_path_field_blank_becomes_none():
    from bi_terminal.specs.fields import ImagePathField

    r, out, fds = _make(b"\r")
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
    r, out, fds = _make(b"\x1b")
    result = r.show_confirm(ConfirmSpec(prompt="Delete?", default=False))
    _close(fds)
    assert result is False


def test_confirm_ignores_unrelated_keys_until_y_or_n():
    r, out, fds = _make(b"qzy")
    result = r.show_confirm(ConfirmSpec(prompt="Delete?"))
    _close(fds)
    assert result is True


# ── show_text_prompt ─────────────────────────────────────────────────────


def test_text_prompt_basic():
    r, out, fds = _make(b"some/path.png\r")
    result = r.show_text_prompt(TextPromptSpec(title="Retry", prompt="Path?"))
    _close(fds)
    assert result == "some/path.png"


def test_text_prompt_cancelled():
    r, out, fds = _make(b"\x1b")
    result = r.show_text_prompt(TextPromptSpec(title="Retry", prompt="Path?"))
    _close(fds)
    assert result is CANCELLED


def test_text_prompt_distinguishes_empty_submit_from_cancel():
    r, out, fds = _make(b"\r")
    result = r.show_text_prompt(
        TextPromptSpec(title="Search", prompt="Query?", distinguish_empty_submit=True)
    )
    _close(fds)
    assert result is EMPTY_SUBMIT


def test_text_prompt_plain_blank_submit_without_the_flag_is_empty_string():
    r, out, fds = _make(b"\r")
    result = r.show_text_prompt(TextPromptSpec(title="Retry", prompt="Path?"))
    _close(fds)
    assert result == ""


# ── show_image / notify ──────────────────────────────────────────────────


def test_show_image_renders_nothing_but_notifies_not_supported():
    """No image rendering (image_capability is fixed at NONE this
    increment) but NOT a silent no-op -- a real, live-reported bug
    (2026-08-10): pressing "View Image(s)" and getting zero feedback at
    all was indistinguishable from the keypress just not working.

    First fix attempt (a bare notify() call) was ALSO reported still
    broken -- the message was written but nothing paced it against the
    very next thing the caller does (_item_detail's loop immediately
    clears the screen again), so a real network-latency caller could never
    actually see it. show_image() must now block on a real keypress before
    returning -- that's what "x" in the input bytes below is standing in
    for; without a real read_key() call in the implementation, this test
    would leave that byte unconsumed rather than hang like a bare empty
    pipe would."""
    r, out, fds = _make(b"x")
    result = r.show_image(["https://example.com/x.png"])
    val = out.getvalue()
    _close(fds)
    assert result is None
    assert "aren't supported" in val.lower()
    assert "press any key" in val.lower()


def test_notify_error_severity_has_marker():
    r, out, fds = _make(b"")
    r.notify("Something broke", severity="error")
    _close(fds)
    assert "[!]" in out.getvalue()
    assert "Something broke" in out.getvalue()


def test_notify_warning_severity_has_marker():
    r, out, fds = _make(b"")
    r.notify("Heads up", severity="warning")
    _close(fds)
    assert "[*]" in out.getvalue()


def test_notify_information_severity_plain():
    r, out, fds = _make(b"")
    r.notify("All good", severity="information")
    _close(fds)
    assert "All good" in out.getvalue()
