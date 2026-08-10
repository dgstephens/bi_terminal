"""AnsiRenderer — the generic stdio ANSI/BBS door renderer.

Text-only (README "Sequencing", step 4): image_capability is fixed at NONE
this increment — show_image is correctly a no-op per the Renderer
contract's documented NONE behavior (unlike the Textual renderer's
deliberate override — this renderer genuinely has no image-rendering code
yet, so the generic contract applies exactly as designed).

Full-screen clear+redraw per interaction, no persistent widget tree — a
plain print-based line-oriented UI. This mirrors bi_python's own original
rich.console era (before its Textual rewrite), which did the same
"_clear()+reprint every keystroke" thing for its filter picker — not a
regression, a deliberate, precedented simplicity for a dumb line terminal.
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
from .ansi_codes import BASE_SGR, CLEAR_SCREEN, CYAN, DIM, RED, WHITE, YELLOW, colored
from .io import AnsiIO, read_line

_MAX_VISIBLE_CHOICES = 15


def _style_detail_line(line: str) -> str:
    """ANSI-flavored twin of renderers/textual/screens.py's
    _style_detail_line — same "label: value" convention (produced by
    specs.menus._detail_prompt), colored via ANSI SGR codes instead of
    Textual markup."""
    if not line:
        return ""
    if ": " in line:
        label, _, value = line.partition(": ")
        return colored(label, CYAN) + ": " + colored(value, WHITE)
    return colored(line, WHITE)


def _nav_hint() -> str:
    parts = [colored(f"[{key}]", YELLOW) + f" {label}" for key, (_dest, label) in sorted(NAV_TARGETS.items())]
    parts.append(colored("[Esc]", YELLOW) + " Back")
    return "  ".join(parts)


class AnsiRenderer:
    image_capability = ImageCapability.NONE

    def __init__(self, io: AnsiIO) -> None:
        self.io = io

    def _header(self, title: str) -> None:
        # BASE_SGR before the clear, not after — a real terminal fills the
        # freshly-erased area with whatever background is active AT THE
        # MOMENT of the erase. See ansi_codes.py's BASE_SGR docstring.
        self.io.write(BASE_SGR)
        self.io.write(CLEAR_SCREEN)
        self.io.write(colored(f"BinInventory -- {title}", CYAN) + "\n")
        self.io.write(colored("=" * 60, CYAN) + "\n\n")

    # ── Action menu ──────────────────────────────────────────────────────

    def show_action_menu(self, spec: ActionMenuSpec) -> Any:
        while True:
            self._header(spec.title)
            if spec.prompt:
                for line in spec.prompt.split("\n"):
                    self.io.write(_style_detail_line(line) + "\n")
                self.io.write("\n")
            for item in spec.items:
                if item.separator:
                    self.io.write(colored("-" * 40, DIM) + "\n")
                    continue
                self.io.write(colored(f"[{item.shortcut.upper()}]", YELLOW) + f" {item.label}\n")
            self.io.write("\n")
            if spec.nav_enabled:
                self.io.write(_nav_hint() + "\n")

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
        # Snap the highlight to spec.initial_value's matching choice exactly
        # once, on the very first render pass (query=="" -> every choice
        # matches, so its real position in `items` is findable) -- then
        # never again, so normal up/down/typing behaves exactly as before.
        # Without this, ComboFilterSelectField's use of this same picker
        # (the Bin field in Edit Item) always highlighted whichever bin
        # sorted first rather than the item's actual current bin -- a real
        # bug where saving without deliberately re-picking the bin could
        # silently reassign it to the wrong one. See ListPickerSpec.initial_value.
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
                self.io.write(colored(line, YELLOW) + "\n")
            if spec.extra_lines:
                self.io.write("\n")
            if spec.prompt:
                self.io.write(colored(spec.prompt, WHITE) + "\n\n")
            self.io.write(f"Filter: {query}\n\n")
            visible = items[scroll : scroll + _MAX_VISIBLE_CHOICES]
            for i, c in enumerate(visible):
                idx = scroll + i
                marker = "> " if idx == highlight else "  "
                if idx == highlight:
                    self.io.write(colored(f"{marker}{c.name}", YELLOW) + "\n")
                else:
                    self.io.write(f"{marker}{c.name}\n")
            if len(items) > _MAX_VISIBLE_CHOICES:
                shown = f"{scroll + 1}-{scroll + len(visible)} of {len(items)}"
                self.io.write(colored(f"  ... showing {shown}", DIM) + "\n")
            self.io.write(
                "\n"
                + colored("Up/Down", YELLOW)
                + " select   "
                + colored("Enter", YELLOW)
                + " choose   "
                + colored("Esc", YELLOW)
                + " cancel\n"
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
            if key in (None, "tab", "left", "right", "unknown-csi"):
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

        # Validate once every field has an answer, matching FormScreen's
        # contract (Textual renderer): only re-prompt the SPECIFIC failing
        # field, not the whole form from scratch.
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
            self.io.write(colored(error, RED) + "\n\n")
            result = self._prompt_field(f)
            if result is CANCELLED:
                return CANCELLED
            values[f.name] = result

    def _prompt_field(self, f) -> Any:
        req = " (required)" if f.required else ""
        if isinstance(f, PasswordField):
            self.io.write(colored(f.label, CYAN) + req + " (leave blank to keep current): ")
            return read_line(self.io, password=True)
        if isinstance(f, TextField):
            self.io.write(colored(f.label, CYAN) + req + ": ")
            return read_line(self.io, initial=f.default)
        if isinstance(f, ImagePathField):
            self.io.write(colored(f.label, CYAN) + f" ({f.hint}): ")
            raw = read_line(self.io, initial=f.default)
            if raw is CANCELLED:
                return CANCELLED
            return raw or None
        if isinstance(f, MultiImagePathField):
            self.io.write(colored(f.label, CYAN) + " (comma-separated file paths): ")
            raw = read_line(self.io, initial=f.default)
            if raw is CANCELLED:
                return CANCELLED
            paths = [p.strip() for p in raw.split(",") if p.strip()]
            return paths or None
        if isinstance(f, SwitchField):
            default_letter = "Y" if f.default else "N"
            self.io.write(colored(f.label, CYAN) + f" (Y/N) [{default_letter}]: ")
            while True:
                key = self.io.read_key()
                if key in ("escape", "ctrl+c"):
                    self.io.write("\n")
                    return CANCELLED
                if key and key.lower() == "y":
                    self.io.write("Y\n")
                    return True
                if key and key.lower() == "n":
                    self.io.write("N\n")
                    return False
                if key == "enter":
                    self.io.write(f"{default_letter}\n")
                    return f.default
        if isinstance(f, TextAreaField):
            self.io.write(colored(f.label, CYAN) + " (single line — multi-line editing not yet supported in the ANSI door): ")
            return read_line(self.io, initial=f.default)
        if isinstance(f, ComboFilterSelectField):
            # Reuses the exact same filter+arrow-select loop as a top-level
            # list picker, scoped to this field's choices — DRY, and Escape
            # here correctly cancels the whole form (CANCELLED propagates
            # straight up), matching the documented contract. initial_value
            # is load-bearing, not cosmetic — see ListPickerSpec.initial_value.
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
            self.io.write(
                colored(f.label, CYAN)
                + f": {n} image{'s' if n != 1 else ''} "
                + colored("(not editable in the text-only ANSI door yet)", DIM)
                + "\n"
            )
            return list(f.images)  # unchanged passthrough
        raise TypeError(f"AnsiRenderer: unhandled field type {type(f)!r}")

    # ── Confirm ──────────────────────────────────────────────────────────

    def show_confirm(self, spec: ConfirmSpec) -> bool:
        self._header("Confirm")
        self.io.write(colored(spec.prompt, WHITE) + "\n\n")
        self.io.write(colored("[Y]", YELLOW) + "es   " + colored("[N]", YELLOW) + "o\n")
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
        self.io.write(colored(spec.prompt, WHITE) + "\n\n")
        result = read_line(self.io, password=spec.password, initial=spec.default)
        if result is CANCELLED:
            return CANCELLED
        if not result and spec.distinguish_empty_submit:
            return EMPTY_SUBMIT
        return result

    # ── Image / notify ───────────────────────────────────────────────────

    def show_image(self, urls: List[str], start_index: int = 0) -> None:
        # image_capability is fixed at NONE this increment — no-op per the
        # documented Renderer contract (see module docstring).
        return None

    def notify(self, message: str, severity: str = "information") -> None:
        color = {"error": RED, "warning": YELLOW}.get(severity, WHITE)
        prefix = {"error": "[!] ", "warning": "[*] "}.get(severity, "")
        self.io.write(colored(prefix + message, color) + "\n")
