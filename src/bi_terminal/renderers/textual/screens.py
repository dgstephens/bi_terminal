"""Textual Screen subclasses consuming bi_terminal.specs specs.

ActionMenuTextualScreen was built in the tracer-bullet increment (README
"Sequencing", step 2). This file now adds every other screen type needed for
full parity with bi_python: ListPickerTextualScreen, ConfirmTextualScreen,
TextPromptTextualScreen, the generic FormScreen (one implementation for all
six of bi_python's bespoke form screens — see the plan's design decision 1),
ImagePreviewTextualScreen, and the internal _ImageManagerScreen.
"""

import asyncio
from typing import List

from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Input, Label, OptionList, Static
from textual.widgets.option_list import Option

from ...core.flow import NAV_TARGETS, GlobalNavigate
from ...core.fuzzy import fuzzy_match
from ...specs.base import CANCELLED, EMPTY_SUBMIT
from ...specs.fields import (
    ActionMenuSpec,
    Choice,
    ComboFilterSelectField,
    ConfirmSpec,
    FieldSpec,
    FormSpec,
    ImageManagerField,
    ImagePathField,
    ListPickerSpec,
    MultiImagePathField,
    PasswordField,
    SwitchField,
    TextAreaField,
    TextField,
    TextPromptSpec,
)
from .._shared_ansi_art import image_to_renderable
from .markup import lit
from .widgets import (
    RetroInput,
    RetroSwitch,
    RetroTextArea,
    _ComboFilterInput,
    _ComboOptionList,
    _ImgCountWidget,
)


def _style_detail_line(line: str) -> str:
    """Re-applies bi_python's cyan-label/white-value detail-field styling to
    a plain "label: value" line — the convention specs.menus._detail_prompt
    produces. Styling lives here (renderer-side) rather than in specs/,
    which deliberately only owns the missing-value policy (the em dash), not
    display/color decisions — see core.models.field_line's docstring."""
    if not line:
        return ""
    if ": " in line:
        label, _, value = line.partition(": ")
        return f"[#55ffff]{lit(label)}[/#55ffff] : [white]{lit(value)}[/white]"
    return f"[white]{lit(line)}[/white]"


def _nav_hint() -> str:
    """The global-nav footer line: [1] Main  [2] Bins  [3] Items  [4] Search  [Esc] Back."""
    parts = []
    for key in sorted(NAV_TARGETS):
        _dest, label = NAV_TARGETS[key]
        parts.append(
            f"[#55ffff]{lit('[')}[/#55ffff][bold #55ffff]{key}[/bold #55ffff]"
            f"[#55ffff]{lit(']')}[/#55ffff][#5555aa] {label}  [/#5555aa]"
        )
    parts.append(f"[#55ffff]{lit('[Esc]')}[/#55ffff][#5555aa] Back  [/#5555aa]")
    return "".join(parts)


# ── Action menu (from the tracer bullet, now with full styling/footer) ──────


class ActionMenuTextualScreen(Screen):
    """Renders an ActionMenuSpec: single-keypress shortcuts dismiss
    immediately (no Enter needed), matching bi_python's ActionMenuScreen
    behavior and the contract documented on
    renderers.base.Renderer.show_action_menu."""

    BINDINGS = [Binding("escape,ctrl+c", "cancel", priority=True)]

    def __init__(self, spec: ActionMenuSpec) -> None:
        super().__init__()
        self.spec = spec

    def compose(self):
        yield Static(f"BinInventory  --  {lit(self.spec.title)}", id="form-title")
        with Vertical(id="picker-body"):
            if self.spec.prompt:
                for line in self.spec.prompt.split("\n"):
                    yield Static(_style_detail_line(line))
                yield Static("")
            for item in self.spec.items:
                if item.separator:
                    yield Static("[#55ffff]" + "─" * 34 + "[/#55ffff]")
                    continue
                yield Static(
                    f"[bold #ffff55]{lit('[' + item.shortcut.upper() + ']')}[/bold #ffff55]"
                    f"  [white]{lit(item.label)}[/white]"
                )
            yield Static("")
            yield Static("[#55ffff]" + "─" * 48 + "[/#55ffff]")
            if self.spec.nav_enabled:
                yield Static(_nav_hint())

    def on_mount(self) -> None:
        self.app.dark = True

    def on_key(self, event) -> None:
        key = event.key.lower()
        if key in ("escape", "ctrl+c"):
            self.dismiss(CANCELLED)
            return
        if self.spec.nav_enabled and key in NAV_TARGETS:
            dest, _label = NAV_TARGETS[key]
            self.dismiss(GlobalNavigate(dest))
            return
        for item in self.spec.items:
            if item.separator or item.shortcut is None:
                continue
            if key == item.shortcut.lower():
                self.dismiss(item.value)
                return

    def action_cancel(self) -> None:
        self.dismiss(CANCELLED)


# ── List picker ──────────────────────────────────────────────────────────


class _PickerInput(RetroInput):
    """The filter box: handles all keys directly, drives the OptionList
    below it. Focus never leaves this Input — you never Tab into the list;
    arrows/Enter/Esc all work from the filter box itself."""

    def on_key(self, event) -> None:
        screen = self.screen
        if not isinstance(screen, ListPickerTextualScreen):
            return
        key = event.key
        if key in ("escape", "ctrl+c"):
            event.stop()
            event.prevent_default()
            screen.dismiss(CANCELLED)
        elif key == "enter":
            event.stop()
            event.prevent_default()
            screen.confirm_selection()
        elif key == "up":
            event.stop()
            event.prevent_default()
            screen.move_highlight(-1)
        elif key == "down":
            event.stop()
            event.prevent_default()
            screen.move_highlight(1)
        # else: let normal typing/backspace fall through to Input's own
        # handling, which fires Input.Changed -> on_input_changed -> refilter.


class ListPickerTextualScreen(Screen):
    """Type-to-filter list picker consuming a ListPickerSpec. Dismisses with
    the selected Choice's value, or CANCELLED."""

    BINDINGS = [Binding("escape,ctrl+c", "cancel", priority=True)]

    def __init__(self, spec: ListPickerSpec) -> None:
        super().__init__()
        self.spec = spec
        self._items: List[Choice] = []
        self._highlight = 0

    def compose(self):
        yield Static(f"BinInventory  --  {lit(self.spec.title)}", id="form-title")
        with Vertical(id="picker-body"):
            for line in self.spec.extra_lines:
                yield Static(f"[#ffff55]{lit(line)}[/#ffff55]")
            if self.spec.extra_lines:
                yield Static("")
            if self.spec.prompt:
                yield Static(f"[bold white]{lit(self.spec.prompt)}[/bold white]")
                yield Static("")
            yield _PickerInput(id="picker_filter", placeholder="type to filter...")
            yield OptionList(id="picker_list", markup=False)
        yield Static(
            "  [bold cyan]↑↓[/bold cyan]  Select    "
            "[bold cyan]Enter[/bold cyan]  Choose    "
            "[bold cyan]Esc[/bold cyan]  Cancel",
            id="footer",
        )

    def on_mount(self) -> None:
        self.app.dark = True
        self._refilter("")
        self.query_one("#picker_filter", RetroInput).focus()

    def _refilter(self, query: str) -> None:
        matches = sorted(
            (
                (span, c)
                for c in self.spec.choices
                for span in [fuzzy_match(query, c.name)]
                if span is not None
            ),
            key=lambda m: m[0],
        )
        self._items = [c for _, c in matches]
        self._highlight = 0
        opt_list = self.query_one("#picker_list", OptionList)
        opt_list.clear_options()
        for c in self._items:
            opt_list.add_option(Option(c.name))
        if self._items:
            opt_list.highlighted = 0

    def on_input_changed(self, event) -> None:
        if event.input.id == "picker_filter":
            self._refilter(event.value.strip())

    def move_highlight(self, delta: int) -> None:
        if not self._items:
            return
        self._highlight = (self._highlight + delta) % len(self._items)
        self.query_one("#picker_list", OptionList).highlighted = self._highlight

    def confirm_selection(self) -> None:
        if self._items:
            self.dismiss(self._items[self._highlight].value)

    def on_option_list_option_highlighted(self, event) -> None:
        self._highlight = event.option_index

    def on_option_list_option_selected(self, event) -> None:
        self._highlight = event.option_index
        self.confirm_selection()

    def action_cancel(self) -> None:
        self.dismiss(CANCELLED)


# ── Confirm ──────────────────────────────────────────────────────────────


class ConfirmTextualScreen(Screen):
    """Yes/No confirmation consuming a ConfirmSpec. Dismisses True/False —
    Esc/Ctrl+C resolve to spec.default (no CANCELLED state needed here)."""

    BINDINGS = [Binding("escape,ctrl+c", "cancel", priority=True)]

    def __init__(self, spec: ConfirmSpec) -> None:
        super().__init__()
        self.spec = spec

    def compose(self):
        yield Static("BinInventory  --  Confirm", id="form-title")
        with Vertical(id="picker-body"):
            yield Static(f"[bold white]{lit(self.spec.prompt)}[/bold white]")
            yield Static("")
            yield Static(
                f"[bold #ffff55]{lit('[Y]')}[/bold #ffff55][white]es[/white]     "
                f"[bold #ffff55]{lit('[N]')}[/bold #ffff55][white]o[/white]"
            )

    def on_mount(self) -> None:
        self.app.dark = True

    def on_key(self, event) -> None:
        key = event.key.lower()
        if key in ("escape", "ctrl+c"):
            self.dismiss(self.spec.default)
        elif key == "n":
            self.dismiss(False)
        elif key == "y":
            self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(self.spec.default)


# ── Text prompt ──────────────────────────────────────────────────────────


class TextPromptTextualScreen(Screen):
    """Single-line text prompt consuming a TextPromptSpec. Dismisses the
    entered string, EMPTY_SUBMIT on a deliberate blank Enter when
    spec.distinguish_empty_submit is True, or CANCELLED."""

    BINDINGS = [Binding("escape,ctrl+c", "cancel", priority=True)]

    def __init__(self, spec: TextPromptSpec) -> None:
        super().__init__()
        self.spec = spec

    def compose(self):
        yield Static(f"BinInventory  --  {lit(self.spec.title)}", id="form-title")
        with Vertical(id="picker-body"):
            yield Static(f"[bold white]{lit(self.spec.prompt)}[/bold white]")
            yield Static("")
            yield RetroInput(id="prompt_input", value=self.spec.default, password=self.spec.password)
        yield Static(
            "[bold #55ffff]Enter[/bold #55ffff][#5555aa]  Submit    [/#5555aa]"
            "[bold #55ffff]Esc[/bold #55ffff][#5555aa]  Cancel[/#5555aa]",
            id="footer",
        )

    def on_mount(self) -> None:
        self.app.dark = True
        self.query_one("#prompt_input", RetroInput).focus()

    def on_input_submitted(self, event) -> None:
        value = event.value.strip()
        if not value and self.spec.distinguish_empty_submit:
            self.dismiss(EMPTY_SUBMIT)
        else:
            self.dismiss(value)

    def action_cancel(self) -> None:
        self.dismiss(CANCELLED)


# ── Image manager (internal — pushed by FormScreen, not a Renderer method) ──


class _ImageManagerScreen(Screen):
    """Generic image manager — view/delete a list of images. Pushed by
    FormScreen for any ImageManagerField. on_done receives the final trimmed
    image list; FormScreen merges it back into its own in-progress state.
    This callback contract is a Textual-internal implementation detail (a
    nested push from within an already-open form) — the *external* contract
    every renderer's show_form() honors (one dismiss-value dict) is
    unaffected; see specs.fields.ImageManagerField's docstring."""

    BINDINGS = [
        Binding("escape", "done", "Done"),
        Binding("d", "delete_selected", "Delete"),
    ]

    def __init__(self, images: List[str], image_mode: str = "none", on_done=None) -> None:
        super().__init__()
        self._images = list(images)
        self._image_mode = image_mode
        self._on_done = on_done

    def compose(self):
        yield Static("", id="form-title")
        yield Static("↑↓: select   D: delete   Esc: done", id="form-hint")
        yield Static("[dim]Select an image to preview[/dim]", id="img-preview")
        yield DataTable(id="img-tbl", cursor_type="row", show_header=False)
        yield Static(
            "  [bold cyan]↑↓[/bold cyan]  Navigate    "
            "[bold cyan]D[/bold cyan]  Delete selected    "
            "[bold cyan]Esc[/bold cyan]  Done",
            id="footer",
        )

    def on_mount(self) -> None:
        self.app.dark = True
        tbl = self.query_one(DataTable)
        tbl.add_column("Image", width=80)
        self._rebuild()

    def _rebuild(self) -> None:
        tbl = self.query_one(DataTable)
        tbl.clear()
        for url in self._images:
            tbl.add_row(url.split("/")[-1])
        n = len(self._images)
        self.query_one("#form-title", Static).update(
            f"BinInventory  --  Manage Images  ({n} image{'s' if n != 1 else ''})"
        )

    def on_data_table_row_highlighted(self, event) -> None:
        idx = event.cursor_row
        if 0 <= idx < len(self._images):
            url = self._images[idx]
            preview = self.query_one("#img-preview", Static)
            preview.update("[dim]Loading...[/dim]")
            self.run_worker(self._fetch_preview(url), exclusive=True)

    async def _fetch_preview(self, url: str) -> None:
        loop = asyncio.get_event_loop()
        renderable = await loop.run_in_executor(None, image_to_renderable, url, self._image_mode)
        try:
            preview = self.query_one("#img-preview", Static)
            preview.update(renderable if renderable is not None else "[dim](no preview available)[/dim]")
        except Exception:
            pass

    def action_delete_selected(self) -> None:
        tbl = self.query_one(DataTable)
        idx = tbl.cursor_row
        if self._images and 0 <= idx < len(self._images):
            self._images.pop(idx)
            self._rebuild()
            self.query_one("#img-preview", Static).update("[dim]Select an image to preview[/dim]")
            if self._images:
                try:
                    tbl.move_cursor(row=min(idx, len(self._images) - 1))
                except Exception:
                    pass

    def action_done(self) -> None:
        if self._on_done is not None:
            self._on_done(list(self._images))
        self.app.pop_screen()


# ── Generic form ─────────────────────────────────────────────────────────


class FormScreen(Screen):
    """One generic form screen for every FormSpec — bin/item/profile/search/
    login/signup. See the plan's design decision 1 for why this replaces
    bi_python's six near-duplicate _XFormScreen classes: FormSpec's typed
    fields (specs/fields.py) already carry everything a form-per-type
    dispatch needs (widget kind, label, required-ness, validator), so one
    real implementation covers all of them instead of six hand-written
    copies each re-solving the same problem slightly differently."""

    BINDINGS = [
        Binding("ctrl+s", "save", "Save"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, spec: FormSpec, image_mode: str = "none") -> None:
        super().__init__()
        self.spec = spec
        self._image_mode = image_mode
        self._image_manager_state = {
            f.name: list(f.images) for f in spec.fields if isinstance(f, ImageManagerField)
        }
        self._combo_filtered = {
            f.name: list(f.choices) for f in spec.fields if isinstance(f, ComboFilterSelectField)
        }
        self._syncing_combo: dict = {}

    # ── compose ──────────────────────────────────────────────────────

    def compose(self):
        yield Static(f"BinInventory  --  {lit(self.spec.title)}", id="form-title")
        yield Static("Tab/Shift+Tab: move between fields   Ctrl+S: save   Esc: cancel", id="form-hint")
        with ScrollableContainer(id="fields"):
            for f in self.spec.fields:
                yield from self._compose_field(f)
        yield Static(
            f"  [bold cyan]Ctrl+S[/bold cyan]  {lit(self.spec.submit_label)}       "
            "[bold cyan]Esc[/bold cyan]  Cancel",
            id="footer",
        )

    def _label_classes(self, f: FieldSpec, top: bool = False) -> str:
        base = "lbl-top" if top else "lbl"
        return f"{base} lbl-req" if f.required else base

    def _compose_field(self, f: FieldSpec):
        if isinstance(f, TextField):
            with Horizontal(classes="row"):
                yield Label(f"{f.label} :", classes=self._label_classes(f))
                yield RetroInput(value=f.default, id=f.name, placeholder=f.placeholder)
        elif isinstance(f, PasswordField):
            with Horizontal(classes="row"):
                yield Label(f"{f.label} :", classes=self._label_classes(f))
                yield RetroInput(
                    value=f.default, id=f.name, password=True, placeholder=f.placeholder
                )
        elif isinstance(f, SwitchField):
            with Horizontal(classes="row"):
                yield Label(f"{f.label} :", classes=self._label_classes(f))
                yield RetroSwitch(value=f.default, id=f.name)
                yield Static("  Space to toggle ON / OFF", classes="toggle-hint")
        elif isinstance(f, TextAreaField):
            with Horizontal(classes="multirow"):
                yield Label(f"{f.label} :", classes=self._label_classes(f, top=True))
                yield RetroTextArea(f.default, id=f.name, tab_behavior="focus")
        elif isinstance(f, ComboFilterSelectField):
            current_name = next((c.name for c in f.choices if c.value == f.default_value), "")
            with Horizontal(classes="binrow"):
                yield Label(f"{f.label} :", classes=self._label_classes(f, top=True))
                with Vertical(classes="bin-picker"):
                    yield _ComboFilterInput(
                        value=current_name,
                        id=f"combo_filter_{f.name}",
                        placeholder="type to filter...",
                    )
                    yield _ComboOptionList(id=f"combo_list_{f.name}", markup=False)
        elif isinstance(f, ImagePathField):
            with Horizontal(classes="row"):
                yield Label(f"{f.label} :", classes=self._label_classes(f))
                yield RetroInput(value=f.default, id=f.name, placeholder=f.hint)
        elif isinstance(f, MultiImagePathField):
            with Horizontal(classes="row"):
                yield Label(f"{f.label} :", classes=self._label_classes(f))
                yield RetroInput(
                    value=f.default, id=f.name, placeholder="comma-separated file paths"
                )
        elif isinstance(f, ImageManagerField):
            n = len(self._image_manager_state[f.name])
            with Horizontal(classes="row"):
                yield Label(f"{f.label} :", classes=self._label_classes(f))
                yield _ImgCountWidget(
                    f"{n} image{'s' if n != 1 else ''}  —  Press [bold cyan]Enter[/bold cyan]",
                    id=f.name,
                    classes="info-row",
                )
        else:
            raise TypeError(f"FormScreen: unhandled field type {type(f)!r}")

    # ── mount / focus ────────────────────────────────────────────────

    def _focus_selector(self, f: FieldSpec) -> str:
        if isinstance(f, ComboFilterSelectField):
            return f"#combo_filter_{f.name}"
        return f"#{f.name}"

    def _field_by_name(self, name: str) -> FieldSpec:
        return next(f for f in self.spec.fields if f.name == name)

    def on_mount(self) -> None:
        self.app.dark = True
        for f in self.spec.fields:
            if isinstance(f, ComboFilterSelectField):
                self._populate_combo(f.name, query="", keep_value=f.default_value)
                self.query_one(f"#combo_list_{f.name}", OptionList).display = False
                # Pre-filling the filter Input's value= fires Input.Changed
                # *asynchronously* (a Textual timing quirk confirmed during
                # bi_python's own conversion) — reassert the full list after
                # that settles, same call_after_refresh pattern used there.
                self.call_after_refresh(
                    lambda fname=f.name, keep=f.default_value: self._populate_combo(
                        fname, query="", keep_value=keep
                    )
                )
        if self.spec.fields:
            try:
                self.query_one(self._focus_selector(self.spec.fields[0])).focus()
            except Exception:
                pass

    # ── combo field behavior ─────────────────────────────────────────

    def _populate_combo(self, field_name: str, query: str = "", keep_value=None) -> None:
        f = self._field_by_name(field_name)
        opt_list = self.query_one(f"#combo_list_{field_name}", OptionList)
        matches = sorted(
            (
                (span, c)
                for c in f.choices
                for span in [f.filter_fn(query, c.name)]
                if span is not None
            ),
            key=lambda m: m[0],
        )
        self._combo_filtered[field_name] = [c for _, c in matches]
        opt_list.clear_options()
        for c in self._combo_filtered[field_name]:
            opt_list.add_option(Option(c.name))
        if matches:
            idx = 0
            if keep_value is not None:
                for i, c in enumerate(self._combo_filtered[field_name]):
                    if c.value == keep_value:
                        idx = i
                        break
            opt_list.highlighted = idx

    def _maybe_close_combos(self) -> None:
        focused = self.focused
        focused_id = focused.id if focused is not None else None
        for opt_list in self.query(_ComboOptionList):
            field_name = opt_list.id[len("combo_list_") :]
            if focused_id not in (f"combo_filter_{field_name}", opt_list.id):
                opt_list.display = False

    def on_input_changed(self, event) -> None:
        input_id = event.input.id or ""
        if input_id.startswith("combo_filter_"):
            field_name = input_id[len("combo_filter_") :]
            if self._syncing_combo.get(field_name):
                self._syncing_combo[field_name] = False
                return
            self._populate_combo(field_name, query=event.value.strip())

    def on_option_list_option_highlighted(self, event) -> None:
        list_id = event.option_list.id or ""
        if not list_id.startswith("combo_list_") or self.focused is not event.option_list:
            return
        field_name = list_id[len("combo_list_") :]
        try:
            self._syncing_combo[field_name] = True
            self.query_one(f"#combo_filter_{field_name}", Input).value = event.option.prompt
        except Exception:
            pass

    def on_option_list_option_selected(self, event) -> None:
        list_id = event.option_list.id or ""
        if not list_id.startswith("combo_list_"):
            return
        field_name = list_id[len("combo_list_") :]
        idx = next((i for i, f in enumerate(self.spec.fields) if f.name == field_name), None)
        if idx is not None and idx + 1 < len(self.spec.fields):
            try:
                self.query_one(self._focus_selector(self.spec.fields[idx + 1])).focus()
            except Exception:
                pass

    # ── image manager integration ────────────────────────────────────

    def action_manage_images(self, field_name: str) -> None:
        images = self._image_manager_state.get(field_name, [])
        if not images:
            self.notify("No images to manage.", severity="warning")
            return
        self.app.push_screen(
            _ImageManagerScreen(
                images,
                image_mode=self._image_mode,
                on_done=lambda imgs, fname=field_name: self._on_images_managed(fname, imgs),
            )
        )

    def _on_images_managed(self, field_name: str, images: List[str]) -> None:
        self._image_manager_state[field_name] = images
        n = len(images)
        try:
            widget = self.query_one(f"#{field_name}", _ImgCountWidget)
            widget.update(
                f"{n} image{'s' if n != 1 else ''}  —  Press [bold cyan]Enter[/bold cyan]"
                if n > 0
                else "No images remaining"
            )
        except Exception:
            pass

    # ── save / cancel ────────────────────────────────────────────────

    def action_save(self) -> None:
        values = {}
        for f in self.spec.fields:
            if isinstance(f, PasswordField):
                values[f.name] = self.query_one(f"#{f.name}", Input).value
            elif isinstance(f, TextField):
                values[f.name] = self.query_one(f"#{f.name}", Input).value.strip()
            elif isinstance(f, ImagePathField):
                values[f.name] = self.query_one(f"#{f.name}", Input).value.strip() or None
            elif isinstance(f, MultiImagePathField):
                raw = self.query_one(f"#{f.name}", Input).value.strip()
                paths = [p.strip() for p in raw.split(",") if p.strip()]
                values[f.name] = paths or None
            elif isinstance(f, SwitchField):
                values[f.name] = self.query_one(f"#{f.name}", RetroSwitch).value
            elif isinstance(f, TextAreaField):
                values[f.name] = self.query_one(f"#{f.name}", RetroTextArea).text.strip()
            elif isinstance(f, ComboFilterSelectField):
                opt_list = self.query_one(f"#combo_list_{f.name}", OptionList)
                choices = self._combo_filtered.get(f.name) or []
                if opt_list.highlighted is None or opt_list.highlighted >= len(choices):
                    values[f.name] = None
                else:
                    values[f.name] = choices[opt_list.highlighted].value
            elif isinstance(f, ImageManagerField):
                values[f.name] = self._image_manager_state.get(f.name, [])
            else:
                raise TypeError(f"FormScreen: unhandled field type {type(f)!r}")

        for f in self.spec.fields:
            if f.validator is not None:
                error = f.validator(values[f.name])
                if error:
                    self.notify(error, severity="error")
                    try:
                        self.query_one(self._focus_selector(f)).focus()
                    except Exception:
                        pass
                    return

        self.dismiss(values)

    def action_cancel(self) -> None:
        self.dismiss(CANCELLED)


# ── Image preview ────────────────────────────────────────────────────────


class ImagePreviewTextualScreen(Screen):
    """View one or more images, fetched on demand. Left/Right cycle through
    multiple images with wraparound. Esc/Ctrl+C closes (always dismisses
    None — the Renderer.show_image contract has no meaningful result)."""

    BINDINGS = [
        Binding("escape,ctrl+c", "close", "Close", priority=True),
        Binding("left,up", "prev_image", "Previous"),
        Binding("right,down", "next_image", "Next"),
    ]

    def __init__(self, title: str, image_urls: List[str], image_mode: str, start_index: int = 0):
        super().__init__()
        self._title = title
        self._urls = [u for u in image_urls if u]
        self._image_mode = image_mode if image_mode != "none" else "ansi"
        self._index = start_index if self._urls and 0 <= start_index < len(self._urls) else 0

    def compose(self):
        yield Static(f"BinInventory  --  {lit(self._title)}", id="form-title")
        yield Static("", id="img-caption")
        with ScrollableContainer(id="img-preview-scroll"):
            yield Static("[#5555aa]Loading...[/#5555aa]", id="img-preview-content")
        yield Static(
            "[bold #55ffff]←→[/bold #55ffff][#5555aa]  Switch image    [/#5555aa]"
            "[bold #55ffff]Esc[/bold #55ffff][#5555aa]  Close[/#5555aa]",
            id="footer",
        )

    def on_mount(self) -> None:
        self.app.dark = True
        self._load_current()

    def _load_current(self) -> None:
        n = len(self._urls)
        caption = f"[#55ffff]Image {self._index + 1} of {n}[/#55ffff]" if n > 1 else ""
        self.query_one("#img-caption", Static).update(caption)
        self.query_one("#img-preview-content", Static).update("[#5555aa]Loading...[/#5555aa]")
        self.run_worker(self._fetch(), exclusive=True)

    async def _fetch(self) -> None:
        if not self._urls:
            self.query_one("#img-preview-content", Static).update("[#5555aa](no images)[/#5555aa]")
            return
        url = self._urls[self._index]
        loop = asyncio.get_event_loop()
        renderable = await loop.run_in_executor(None, image_to_renderable, url, self._image_mode)
        try:
            self.query_one("#img-preview-content", Static).update(
                renderable if renderable is not None else "[#5555aa](image could not be loaded)[/#5555aa]"
            )
        except Exception:
            pass

    def action_prev_image(self) -> None:
        if len(self._urls) > 1:
            self._index = (self._index - 1) % len(self._urls)
            self._load_current()

    def action_next_image(self) -> None:
        if len(self._urls) > 1:
            self._index = (self._index + 1) % len(self._urls)
            self._load_current()

    def action_close(self) -> None:
        self.dismiss(None)
