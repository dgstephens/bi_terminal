"""PetsciiRenderer — the Commodore 64 door renderer.

image_capability is declared as PETSCII_GRAPHICS (reserved in
renderers/base.py's enum) but show_image stays a no-op this increment —
real hi-res/multicolor charset graphics conversion is substantial, separate
work, explicitly out of scope for "get PETSCII screens working" (matches
how the ANSI renderer shipped text-only first too). Worth flagging clearly
since this is a deliberate exception to the general rule that a non-NONE
capability implies show_image actually does something — don't assume
otherwise from the enum value alone.

40 columns, ~25 rows — narrower and shorter than a generic ANSI terminal,
so every rendered line is truncated (not wrapped) to fit, and the
list-picker's visible-choice window is smaller. No absolute cursor
positioning exists in raw PETSCII (see petscii_codes.py's module
docstring) — every screen is CLR + sequential top-to-bottom print, the same
"full clear+redraw" pattern the ANSI renderer already uses, just without a
move(row, col) primitive to fall back on (there isn't one to have).

Colors are STATEFUL in PETSCII (no SGR-style auto-reset like ANSI) — every
colored span here explicitly sets the color it wants and explicitly
restores WHITE afterward, never relying on an implicit reset.
"""

from typing import Any, List, Union

from ...core.flow import NAV_TARGETS, GlobalNavigate
from ...core.fuzzy import fuzzy_match
from ...specs.base import CANCELLED, EMPTY_SUBMIT
from ...specs.fields import (
    ActionMenuSpec,
    ComboFilterSelectField,
    ConfirmSpec,
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
from ..base import ImageCapability
from . import petscii_codes as pc
from .io import PetsciiIO, read_line
from .sanitize import to_petscii_text

_WIDTH = 39
_MAX_VISIBLE_CHOICES = 9


def _truncate(text: str, width: int = _WIDTH) -> str:
    return text if len(text) <= width else text[: width - 1] + "."


def _enc(text: str) -> bytes:
    return to_petscii_text(text)


def _style_detail_line(line: str) -> bytes:
    """PETSCII-flavored twin of the ANSI/Textual _style_detail_line — same
    "label: value" convention (from specs.menus._detail_prompt), using
    color control bytes instead of markup/SGR."""
    if not line:
        return b""
    if ": " in line:
        label, _, value = line.partition(": ")
        return pc.CYAN + _enc(label) + b": " + pc.WHITE + _enc(value)
    return pc.WHITE + _enc(line)


def _nav_hint() -> bytes:
    parts = []
    for key in sorted(NAV_TARGETS):
        _dest, label = NAV_TARGETS[key]
        parts.append(pc.YELLOW + _enc(f"[{key}]") + pc.WHITE + _enc(f" {label} "))
    parts.append(pc.YELLOW + _enc("[Esc]") + pc.WHITE + _enc(" Back"))
    return b"".join(parts)


class PetsciiRenderer:
    image_capability = ImageCapability.PETSCII_GRAPHICS

    def __init__(self, io: PetsciiIO) -> None:
        self.io = io
        # The default C64 charset has no lowercase letters at all (ASCII
        # 'a'-'z' display as graphics symbols) — must switch once, up
        # front, since bin names/descriptions/etc. are full of lowercase
        # text. See petscii_codes.py's module docstring.
        self.io.write_raw(pc.SWITCH_TO_LOWERCASE)

    def _header(self, title: str) -> None:
        self.io.write_raw(pc.CLR)
        self.io.write_raw(pc.CYAN + _enc(_truncate(title)) + b"\r")

    # ── Action menu ──────────────────────────────────────────────────────

    def show_action_menu(self, spec: ActionMenuSpec) -> Any:
        while True:
            self._header(spec.title)
            if spec.prompt:
                for line in spec.prompt.split("\n"):
                    self.io.write_raw(_style_detail_line(_truncate(line)) + b"\r")
                self.io.write_raw(b"\r")
            for item in spec.items:
                if item.separator:
                    self.io.write_raw(pc.CYAN + _enc("-" * _WIDTH) + b"\r")
                    continue
                self.io.write_raw(
                    pc.YELLOW
                    + _enc(f"[{item.shortcut.upper()}]")
                    + pc.WHITE
                    + _enc(f" {_truncate(item.label, _WIDTH - 5)}")
                    + b"\r"
                )
            self.io.write_raw(b"\r")
            if spec.nav_enabled:
                self.io.write_raw(_nav_hint() + b"\r")

            key = self.io.read_key()
            if key in ("escape", "ctrl+c"):
                return CANCELLED
            if spec.nav_enabled and key in NAV_TARGETS:
                dest, _label = NAV_TARGETS[key]
                return GlobalNavigate(dest)
            if key is None:
                continue
            for item in spec.items:
                if item.separator or item.shortcut is None:
                    continue
                if key.lower() == item.shortcut.lower():
                    return item.value

    # ── List picker ──────────────────────────────────────────────────────

    def show_list_picker(self, spec: ListPickerSpec) -> Any:
        query = ""
        highlight = 0
        scroll = 0
        # See ansi/renderer.py's show_list_picker for why this exists —
        # same bug, same fix, same shared ListPickerSpec.initial_value
        # mechanism (ComboFilterSelectField's Bin field in Edit Item was
        # always highlighting whichever bin sorted first, not the item's
        # actual current bin).
        positioned = spec.initial_value is None
        while True:
            matches = sorted(
                (
                    (span, c)
                    for c in spec.choices
                    for span in [fuzzy_match(query, c.name)]
                    if span is not None
                ),
                key=lambda m: m[0],
            )
            items = [c for _, c in matches]
            if not positioned:
                for i, c in enumerate(items):
                    if c.value == spec.initial_value:
                        highlight = i
                        break
                positioned = True
            if not items:
                highlight = 0
            elif highlight >= len(items):
                highlight = len(items) - 1
            if highlight < scroll:
                scroll = highlight
            elif highlight >= scroll + _MAX_VISIBLE_CHOICES:
                scroll = highlight - _MAX_VISIBLE_CHOICES + 1

            self._header(spec.title)
            for line in spec.extra_lines:
                self.io.write_raw(pc.YELLOW + _enc(_truncate(line)) + b"\r")
            if spec.extra_lines:
                self.io.write_raw(b"\r")
            if spec.prompt:
                self.io.write_raw(pc.WHITE + _enc(_truncate(spec.prompt)) + b"\r\r")
            self.io.write_raw(pc.WHITE + _enc(f"Filter: {query}") + b"\r\r")
            visible = items[scroll : scroll + _MAX_VISIBLE_CHOICES]
            for i, c in enumerate(visible):
                idx = scroll + i
                name = _truncate(c.name, _WIDTH - 2)
                if idx == highlight:
                    self.io.write_raw(pc.REVERSE_ON + _enc(f"> {name}") + pc.REVERSE_OFF + b"\r")
                else:
                    self.io.write_raw(_enc(f"  {name}") + b"\r")
            if len(items) > _MAX_VISIBLE_CHOICES:
                shown = f"{scroll + 1}-{scroll + len(visible)} of {len(items)}"
                self.io.write_raw(pc.CYAN + _enc(f"  ...{shown}") + b"\r")
            self.io.write_raw(
                b"\r"
                + pc.YELLOW
                + _enc("Up/Dn")
                + pc.WHITE
                + _enc(" select ")
                + pc.YELLOW
                + _enc("Ret")
                + pc.WHITE
                + _enc(" choose ")
                + pc.YELLOW
                + _enc("Esc")
                + pc.WHITE
                + _enc(" cancel")
                + b"\r"
            )

            key = self.io.read_key()
            if key in ("escape", "ctrl+c"):
                return CANCELLED
            if key == "enter":
                if items:
                    return items[highlight].value
                continue
            if key == "up":
                if items:
                    highlight = (highlight - 1) % len(items)
                continue
            if key == "down":
                if items:
                    highlight = (highlight + 1) % len(items)
                continue
            if key == "backspace":
                query = query[:-1]
                highlight = 0
                scroll = 0
                continue
            if key in (None, "tab", "left", "right"):
                continue
            query += key
            highlight = 0
            scroll = 0

    # ── Form ─────────────────────────────────────────────────────────────

    def show_form(self, spec: FormSpec) -> Union[dict, Any]:
        values = {}
        for f in spec.fields:
            self._header(spec.title)
            result = self._prompt_field(f)
            if result is CANCELLED:
                return CANCELLED
            values[f.name] = result

        while True:
            failed = None
            for f in spec.fields:
                if f.validator is not None:
                    error = f.validator(values[f.name])
                    if error:
                        failed = (f, error)
                        break
            if failed is None:
                return values
            f, error = failed
            self._header(spec.title)
            self.io.write_raw(pc.RED + _enc(_truncate(error)) + b"\r\r")
            result = self._prompt_field(f)
            if result is CANCELLED:
                return CANCELLED
            values[f.name] = result

    def _prompt_field(self, f) -> Any:
        req = " (req)" if f.required else ""
        if isinstance(f, PasswordField):
            self.io.write_raw(pc.CYAN + _enc(_truncate(f.label + req)) + pc.WHITE + _enc(": "))
            return read_line(self.io, password=True)
        if isinstance(f, TextField):
            self.io.write_raw(pc.CYAN + _enc(_truncate(f.label + req)) + pc.WHITE + _enc(": "))
            return read_line(self.io, initial=f.default)
        if isinstance(f, ImagePathField):
            self.io.write_raw(pc.CYAN + _enc(_truncate(f.label)) + pc.WHITE + _enc(": "))
            raw = read_line(self.io, initial=f.default)
            if raw is CANCELLED:
                return CANCELLED
            return raw or None
        if isinstance(f, MultiImagePathField):
            self.io.write_raw(pc.CYAN + _enc(_truncate(f.label)) + pc.WHITE + _enc(" (comma-sep): "))
            raw = read_line(self.io, initial=f.default)
            if raw is CANCELLED:
                return CANCELLED
            paths = [p.strip() for p in raw.split(",") if p.strip()]
            return paths or None
        if isinstance(f, SwitchField):
            default_letter = "Y" if f.default else "N"
            self.io.write_raw(
                pc.CYAN + _enc(_truncate(f.label)) + pc.WHITE + _enc(f" (Y/N) [{default_letter}]: ")
            )
            while True:
                key = self.io.read_key()
                if key in ("escape", "ctrl+c"):
                    self.io.write_raw(b"\r")
                    return CANCELLED
                if key and key.lower() == "y":
                    self.io.write_text("Y\r")
                    return True
                if key and key.lower() == "n":
                    self.io.write_text("N\r")
                    return False
                if key == "enter":
                    self.io.write_text(f"{default_letter}\r")
                    return f.default
        if isinstance(f, TextAreaField):
            self.io.write_raw(pc.CYAN + _enc(_truncate(f.label)) + pc.WHITE + _enc(" (1 line): "))
            return read_line(self.io, initial=f.default)
        if isinstance(f, ComboFilterSelectField):
            # Reuses the exact same filter+arrow-select loop as a top-level
            # list picker, scoped to this field's choices — matches the
            # ANSI renderer's approach exactly (DRY; Escape here correctly
            # cancels the whole form, CANCELLED propagates straight up).
            # initial_value is load-bearing, not cosmetic — see
            # ListPickerSpec.initial_value.
            return self.show_list_picker(
                ListPickerSpec(
                    title=f.label,
                    prompt=f"Select {f.label}",
                    choices=f.choices,
                    initial_value=f.default_value,
                )
            )
        if isinstance(f, ImageManagerField):
            n = len(f.images)
            self.io.write_raw(
                pc.CYAN
                + _enc(_truncate(f.label))
                + pc.WHITE
                + _enc(f": {n} image{'s' if n != 1 else ''} (not editable yet)")
                + b"\r"
            )
            return list(f.images)  # unchanged passthrough
        raise TypeError(f"PetsciiRenderer: unhandled field type {type(f)!r}")

    # ── Confirm ──────────────────────────────────────────────────────────

    def show_confirm(self, spec: ConfirmSpec) -> bool:
        self._header("Confirm")
        self.io.write_raw(pc.WHITE + _enc(_truncate(spec.prompt)) + b"\r\r")
        self.io.write_raw(
            pc.YELLOW + _enc("[Y]") + pc.WHITE + _enc("es  ") + pc.YELLOW + _enc("[N]") + pc.WHITE + _enc("o") + b"\r"
        )
        while True:
            key = self.io.read_key()
            if key in ("escape", "ctrl+c"):
                return spec.default
            if key and key.lower() == "y":
                return True
            if key and key.lower() == "n":
                return False

    # ── Text prompt ──────────────────────────────────────────────────────

    def show_text_prompt(self, spec: TextPromptSpec) -> Union[str, Any]:
        self._header(spec.title)
        self.io.write_raw(pc.WHITE + _enc(_truncate(spec.prompt)) + b"\r\r")
        result = read_line(self.io, password=spec.password, initial=spec.default)
        if result is CANCELLED:
            return CANCELLED
        if not result and spec.distinguish_empty_submit:
            return EMPTY_SUBMIT
        return result

    # ── Image / notify ───────────────────────────────────────────────────

    def show_image(self, urls: List[str], start_index: int = 0) -> None:
        # See module docstring — a deliberate no-op this increment despite
        # the PETSCII_GRAPHICS capability declaration. Not a SILENT no-op
        # though -- that was indistinguishable from the "View Image(s)"
        # keypress just not working at all, a real live-reported bug
        # (2026-08-10). notify() instead so the user gets an actual answer.
        self.notify("Images aren't supported in this PETSCII display yet.", severity="information")

    def notify(self, message: str, severity: str = "information") -> None:
        color = {"error": pc.RED, "warning": pc.YELLOW}.get(severity, pc.WHITE)
        prefix = {"error": "! ", "warning": "* "}.get(severity, "")
        self.io.write_raw(color + _enc(_truncate(prefix + message)) + b"\r")
