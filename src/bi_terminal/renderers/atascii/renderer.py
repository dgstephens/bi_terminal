"""AtasciiRenderer — the Atari 8-bit door renderer.

image_capability is declared as ATASCII_GRAPHICS (reserved in
renderers/base.py's enum) but show_image stays a no-op this increment —
real ANTIC/GTIA graphics conversion is substantial, separate work,
explicitly out of scope (matches ANSI/PETSCII's same deliberate limit).

Two real differences from PetsciiRenderer, both driven by protocol facts
confirmed before design (see the plan that produced this file), not
stylistic choices:

1. **No character-set switch** — ASCII letters (both cases) already display
   correctly with no setup step, unlike PETSCII's SWITCH_TO_LOWERCASE.
2. **No color codes exist in raw ATASCII at all.** Every colored span the
   ANSI/PETSCII renderers use (cyan labels, yellow shortcuts, red errors)
   has NO equivalent here — the only visual differentiation tool is inverse
   video via atascii_codes.inverse(), which is per-BYTE (set the high bit
   on each character) rather than a persistent on/off mode like PETSCII's
   REVERSE_ON/OFF. Used deliberately for the list-picker's highlighted row;
   everything else renders as plain text with bracket/prefix punctuation
   doing the visual organizing work color would otherwise do.

40 columns, no absolute cursor positioning in raw ATASCII (same as
PETSCII) — every screen is CLR + sequential top-to-bottom print, the same
"full clear+redraw" pattern as every other renderer in this project.

IMPORTANT internal invariant: atascii_codes.inverse() must only ever be
applied to encoded TEXT bytes, never to a control-code byte (e.g. RETURN) —
inverting a control byte produces a completely different, wrong control
code (confirmed: RETURN=155 already has its high bit set, but a byte like
CLR=125 would become 253=BUZZER if accidentally inverted). Every call site
below is careful to invert only the text portion, appending RETURN
afterward, unmodified.
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
from . import atascii_codes as ac
from .io import AtasciiIO, read_line
from .sanitize import to_atascii_text

_WIDTH = 39
_MAX_VISIBLE_CHOICES = 9


def _truncate(text: str, width: int = _WIDTH) -> str:
    return text if len(text) <= width else text[: width - 1] + "."


def _enc(text: str) -> bytes:
    return to_atascii_text(text)


def _style_detail_line(line: str) -> bytes:
    """ATASCII twin of the ANSI/PETSCII _style_detail_line — same "label:
    value" convention, but plain text: there is no color code to apply."""
    return _enc(line)


def _nav_hint() -> bytes:
    parts = []
    for key in sorted(NAV_TARGETS):
        _dest, label = NAV_TARGETS[key]
        parts.append(_enc(f"[{key}] {label} "))
    parts.append(_enc("[Esc] Back"))
    return b"".join(parts)


class AtasciiRenderer:
    image_capability = ImageCapability.ATASCII_GRAPHICS

    def __init__(self, io: AtasciiIO) -> None:
        self.io = io
        # No character-set switch needed — see module docstring.

    def _header(self, title: str) -> None:
        self.io.write_raw(ac.CLR)
        self.io.write_raw(_enc(_truncate(title)) + ac.RETURN)

    # ── Action menu ──────────────────────────────────────────────────────

    def show_action_menu(self, spec: ActionMenuSpec) -> Any:
        while True:
            self._header(spec.title)
            if spec.prompt:
                for line in spec.prompt.split("\n"):
                    self.io.write_raw(_style_detail_line(_truncate(line)) + ac.RETURN)
                self.io.write_raw(ac.RETURN)
            for item in spec.items:
                if item.separator:
                    self.io.write_raw(_enc("-" * _WIDTH) + ac.RETURN)
                    continue
                self.io.write_raw(
                    _enc(f"[{item.shortcut.upper()}] {_truncate(item.label, _WIDTH - 5)}") + ac.RETURN
                )
            self.io.write_raw(ac.RETURN)
            if spec.nav_enabled:
                self.io.write_raw(_nav_hint() + ac.RETURN)

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
                self.io.write_raw(_enc(_truncate(line)) + ac.RETURN)
            if spec.extra_lines:
                self.io.write_raw(ac.RETURN)
            if spec.prompt:
                self.io.write_raw(_enc(_truncate(spec.prompt)) + ac.RETURN + ac.RETURN)
            self.io.write_raw(_enc(f"Filter: {query}") + ac.RETURN + ac.RETURN)
            visible = items[scroll : scroll + _MAX_VISIBLE_CHOICES]
            for i, c in enumerate(visible):
                idx = scroll + i
                name = _truncate(c.name, _WIDTH - 2)
                if idx == highlight:
                    # Inverse video is the ONLY highlight mechanism — see
                    # module docstring. Only the text bytes are inverted;
                    # ac.RETURN (already >=128, a real control byte) is
                    # appended un-inverted, never passed through inverse().
                    self.io.write_raw(ac.inverse(_enc(f"> {name}")) + ac.RETURN)
                else:
                    self.io.write_raw(_enc(f"  {name}") + ac.RETURN)
            if len(items) > _MAX_VISIBLE_CHOICES:
                shown = f"{scroll + 1}-{scroll + len(visible)} of {len(items)}"
                self.io.write_raw(_enc(f"  ...{shown}") + ac.RETURN)
            self.io.write_raw(
                ac.RETURN + _enc("Up/Dn select  Ret choose  Esc cancel") + ac.RETURN
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
            self.io.write_raw(_enc(_truncate(error)) + ac.RETURN + ac.RETURN)
            result = self._prompt_field(f)
            if result is CANCELLED:
                return CANCELLED
            values[f.name] = result

    def _prompt_field(self, f) -> Any:
        req = " (req)" if f.required else ""
        if isinstance(f, PasswordField):
            self.io.write_raw(_enc(_truncate(f.label + req) + ": "))
            return read_line(self.io, password=True)
        if isinstance(f, TextField):
            self.io.write_raw(_enc(_truncate(f.label + req) + ": "))
            return read_line(self.io, initial=f.default)
        if isinstance(f, ImagePathField):
            self.io.write_raw(_enc(_truncate(f.label) + ": "))
            raw = read_line(self.io, initial=f.default)
            if raw is CANCELLED:
                return CANCELLED
            return raw or None
        if isinstance(f, MultiImagePathField):
            self.io.write_raw(_enc(_truncate(f.label) + " (comma-sep): "))
            raw = read_line(self.io, initial=f.default)
            if raw is CANCELLED:
                return CANCELLED
            paths = [p.strip() for p in raw.split(",") if p.strip()]
            return paths or None
        if isinstance(f, SwitchField):
            default_letter = "Y" if f.default else "N"
            self.io.write_raw(_enc(f"{_truncate(f.label)} (Y/N) [{default_letter}]: "))
            while True:
                key = self.io.read_key()
                if key in ("escape", "ctrl+c"):
                    self.io.write_raw(ac.RETURN)
                    return CANCELLED
                if key and key.lower() == "y":
                    self.io.write_text("Y")
                    self.io.write_raw(ac.RETURN)
                    return True
                if key and key.lower() == "n":
                    self.io.write_text("N")
                    self.io.write_raw(ac.RETURN)
                    return False
                if key == "enter":
                    self.io.write_text(default_letter)
                    self.io.write_raw(ac.RETURN)
                    return f.default
        if isinstance(f, TextAreaField):
            self.io.write_raw(_enc(_truncate(f.label) + " (1 line): "))
            return read_line(self.io, initial=f.default)
        if isinstance(f, ComboFilterSelectField):
            # Reuses the exact same filter+arrow-select loop as a top-level
            # list picker, scoped to this field's choices — matches the
            # ANSI/PETSCII renderers' approach exactly (DRY; Escape here
            # correctly cancels the whole form, CANCELLED propagates
            # straight up).
            return self.show_list_picker(
                ListPickerSpec(title=f.label, prompt=f"Select {f.label}", choices=f.choices)
            )
        if isinstance(f, ImageManagerField):
            n = len(f.images)
            self.io.write_raw(
                _enc(f"{_truncate(f.label)}: {n} image{'s' if n != 1 else ''} (not editable yet)")
                + ac.RETURN
            )
            return list(f.images)  # unchanged passthrough
        raise TypeError(f"AtasciiRenderer: unhandled field type {type(f)!r}")

    # ── Confirm ──────────────────────────────────────────────────────────

    def show_confirm(self, spec: ConfirmSpec) -> bool:
        self._header("Confirm")
        self.io.write_raw(_enc(_truncate(spec.prompt)) + ac.RETURN + ac.RETURN)
        self.io.write_raw(_enc("[Y]es  [N]o") + ac.RETURN)
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
        self.io.write_raw(_enc(_truncate(spec.prompt)) + ac.RETURN + ac.RETURN)
        result = read_line(self.io, password=spec.password, initial=spec.default)
        if result is CANCELLED:
            return CANCELLED
        if not result and spec.distinguish_empty_submit:
            return EMPTY_SUBMIT
        return result

    # ── Image / notify ───────────────────────────────────────────────────

    def show_image(self, urls: List[str], start_index: int = 0) -> None:
        # See module docstring — a deliberate no-op this increment despite
        # the ATASCII_GRAPHICS capability declaration.
        return None

    def notify(self, message: str, severity: str = "information") -> None:
        # No color available — the text prefix is the ONLY signal here,
        # not a redundant one alongside color the way ANSI/PETSCII use it.
        prefix = {"error": "! ", "warning": "* "}.get(severity, "")
        self.io.write_raw(_enc(_truncate(prefix + message)) + ac.RETURN)
