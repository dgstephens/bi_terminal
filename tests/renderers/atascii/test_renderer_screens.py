import io as pyio
import os

from bi_terminal.core.flow import GlobalNavigate
from bi_terminal.renderers.atascii import atascii_codes as ac
from bi_terminal.renderers.atascii.io import AtasciiIO
from bi_terminal.renderers.atascii.renderer import AtasciiRenderer
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
    ImagePathField,
    ListPickerSpec,
    MultiImagePathField,
    SwitchField,
    TextField,
    TextPromptSpec,
)

RET = ac.RETURN


def _make(write_bytes: bytes):
    r_fd, w_fd = os.pipe()
    os.write(w_fd, write_bytes)
    out = pyio.BytesIO()
    io_obj = AtasciiIO(r_fd, out)
    return AtasciiRenderer(io_obj), out, (r_fd, w_fd)


def _close(fds):
    for fd in fds:
        try:
            os.close(fd)
        except OSError:
            pass


def test_image_capability_is_atascii_graphics():
    assert AtasciiRenderer.image_capability == ImageCapability.ATASCII_GRAPHICS


def test_construction_sends_no_charset_switch_unlike_petscii():
    """Confirmed protocol difference: ATASCII needs no character-set setup
    at all, unlike PETSCII's SWITCH_TO_LOWERCASE."""
    r, out, fds = _make(b"")
    _close(fds)
    assert out.getvalue() == b""


# ── show_action_menu ─────────────────────────────────────────────────────


def test_action_menu_shortcut_match():
    r, out, fds = _make(b"b")
    spec = ActionMenuSpec(title="Main", items=[ActionItem("My Bins", "b", "bins")], nav_enabled=False)
    result = r.show_action_menu(spec)
    _close(fds)
    assert result == "bins"


def test_action_menu_escape_returns_cancelled():
    r, out, fds = _make(ac.ESCAPE)
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


def test_action_menu_uses_no_color_bytes_at_all():
    """No color codes exist in raw ATASCII (confirmed) -- verify none of
    the ANSI/PETSCII-style color bytes ever get emitted (there's nothing to
    emit them WITH; this proves the renderer doesn't accidentally reuse a
    PETSCII color constant by mistake)."""
    r, out, fds = _make(b"x")
    spec = ActionMenuSpec(title="Main", items=[ActionItem("Exit", "x", "exit")], nav_enabled=False)
    r.show_action_menu(spec)
    val = out.getvalue()
    _close(fds)
    petscii_color_bytes = {144, 5, 28, 159, 156, 30, 31, 158, 129, 149, 150, 151, 152, 153, 154, 155}
    # 155 legitimately appears as ATASCII's own RETURN byte -- exclude it
    # from this check specifically, it's not a color here, it's EOL.
    suspicious = (petscii_color_bytes - {155}) & set(val)
    assert not suspicious


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


def test_list_picker_uses_inverse_video_high_bit_for_highlight():
    r, out, fds = _make(RET)
    spec = ListPickerSpec(title="Items", choices=[Choice("Widget", "w1")])
    r.show_list_picker(spec)
    val = out.getvalue()
    _close(fds)
    # ">" is 0x3E (62); inverted (high bit set) it's 0xBE (190)
    assert bytes([0xBE]) in val
    # and the un-inverted ">" must NOT appear on its own for the highlighted row
    # (every byte of "> Widget" should be inverted, not just some of it)
    inverted_prefix = ac.inverse(b"> Widget")
    assert inverted_prefix in val


def test_list_picker_down_arrow_moves_highlight():
    r, out, fds = _make(bytes([29]) + RET)
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
    r, out, fds = _make(ac.ESCAPE)
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
    assert long_name.encode("ascii") not in val
    assert ac.inverse(long_name.encode("ascii")) not in val


def test_list_picker_scroll_window_for_long_lists():
    choices = [Choice(f"Item {i}", i) for i in range(20)]
    r, out, fds = _make(RET)
    spec = ListPickerSpec(title="Items", choices=choices)
    result = r.show_list_picker(spec)
    val = out.getvalue()
    _close(fds)
    assert result == 0
    assert b"of 20" in val


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
    r, out, fds = _make(b"typed" + ac.ESCAPE)
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
    r, out, fds = _make(ac.ESCAPE)
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


def test_show_image_is_a_noop_despite_declared_capability():
    r, out, fds = _make(b"")
    result = r.show_image(["https://example.com/x.png"])
    _close(fds)
    assert result is None


def test_notify_error_uses_text_prefix_since_no_color_exists():
    r, out, fds = _make(b"")
    r.notify("Something broke", severity="error")
    val = out.getvalue()
    _close(fds)
    assert b"! Something broke" in val


def test_notify_warning_uses_text_prefix():
    r, out, fds = _make(b"")
    r.notify("Heads up", severity="warning")
    val = out.getvalue()
    _close(fds)
    assert b"* Heads up" in val
