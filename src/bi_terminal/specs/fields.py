"""Every field type and screen type in the spec schema.

Each concrete type here corresponds to a screen or form-field concept found
somewhere in bi_python's forms.py/screens.py — see specs/forms.py and
specs/menus.py for the actual per-screen builders that assemble these into
real specs, and the bi_terminal planning session's design report for the
field-by-field mapping this was checked against.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

from ..core.fuzzy import fuzzy_match
from .base import FieldSpec, ScreenSpec

# ── Form fields ──────────────────────────────────────────────────────────


@dataclass
class TextField(FieldSpec):
    default: str = ""
    placeholder: str = ""


@dataclass
class PasswordField(FieldSpec):
    default: str = ""
    placeholder: str = ""


@dataclass
class SwitchField(FieldSpec):
    default: bool = False


@dataclass
class TextAreaField(FieldSpec):
    default: str = ""


@dataclass
class Choice:
    """One entry in a SelectField/ComboFilterSelectField/ListPickerSpec.
    `value` is opaque to the spec layer — a renderer just hands back whatever
    was attached to the chosen entry (e.g. a full bin/item dict, or an
    ("open", item)-style action tag, matching bi_python's convention)."""

    name: str
    value: Any


@dataclass
class SelectField(FieldSpec):
    """Single-select from a fixed, prebuilt list — no live typing/filtering.
    (bi_python didn't actually have a plain non-filtering select field in any
    form — Settings' image-mode choice used an ActionMenuSpec instead — but
    this is reserved for any future form field that needs "pick one of a
    short fixed list" without the combo-filter behavior below.)"""

    choices: List[Choice] = field(default_factory=list)
    default_value: Any = None


@dataclass
class ComboFilterSelectField(FieldSpec):
    """Type-to-filter combo box: bi_python's item-form Bin field. Starts
    collapsed/showing the current value; typing filters `choices` live via
    `filter_fn` (defaults to core.fuzzy.fuzzy_match, matching bi_python's
    default so all renderers filter identically unless a spec explicitly
    overrides it)."""

    choices: List[Choice] = field(default_factory=list)
    default_value: Any = None
    filter_fn: Callable[[str, str], Optional[int]] = fuzzy_match


@dataclass
class ImagePathField(FieldSpec):
    """Local filesystem path to a new image to upload. Blank = no change
    (keep whatever image already exists, if any)."""

    default: str = ""
    hint: str = "Path to image file on disk"


@dataclass
class MultiImagePathField(FieldSpec):
    """Comma-separated local filesystem paths (bi_python's item-form "New
    images" field) — split/stripped into a list by the renderer's form-runner
    before it reaches core.api.create_item/update_item's image_paths arg."""

    default: str = ""


@dataclass
class ImageManagerField(FieldSpec):
    """The "N images — press Enter to manage" row on the Bin/Item forms.

    Activating it is itself a nested screen push (list existing images,
    delete some) whose result — the trimmed `list[str]` of remaining image
    URLs — is merged back into the parent form's in-progress state by the
    renderer's form-runner loop. This is a deliberate normalization versus
    bi_python's `_ImageManagerScreen`, which used a bespoke `on_done`
    callback instead of the dismiss-value contract every other screen here
    uses — one less special case for every renderer to reimplement."""

    images: List[str] = field(default_factory=list)


# ── Screen-level specs ──────────────────────────────────────────────────


@dataclass
class ConfirmSpec(ScreenSpec):
    prompt: str = ""
    default: bool = False
    """No CANCELLED state needed — Esc maps to `default`, matching
    bi_python's ConfirmScreen (y -> True, n/Esc/Ctrl+C -> False)."""


@dataclass
class ActionItem:
    """One row of an ActionMenuSpec. `shortcut` is a single keypress that
    dismisses the menu immediately with `value` — no Enter needed, matching
    bi_python's ActionMenuScreen. A separator row has `separator=True` and
    all other fields ignored/None."""

    label: Optional[str] = None
    shortcut: Optional[str] = None
    value: Any = None
    separator: bool = False


@dataclass
class ActionMenuSpec(ScreenSpec):
    prompt: str = ""
    items: List[ActionItem] = field(default_factory=list)
    nav_enabled: bool = True
    """When True, digits 1-4 dismiss a core.flow.GlobalNavigate("main"/"bins"/
    "items"/"search") regardless of `items` — bi_python's global-nav jump.
    False on screens where global nav is meaningless (pre-auth Login/Signup/
    Exit choice, and the main menu itself since jumping to where you already
    are is a no-op)."""


@dataclass
class TextPromptSpec(ScreenSpec):
    prompt: str = ""
    default: str = ""
    password: bool = False
    distinguish_empty_submit: bool = False
    """When True, a deliberate blank Enter dismisses EMPTY_SUBMIT rather than
    "" — needed for exactly one bi_python case (the search box) but exposed
    generically here in case a future screen needs the same distinction."""


@dataclass
class ListPickerSpec(ScreenSpec):
    prompt: str = ""
    choices: List[Choice] = field(default_factory=list)
    extra_lines: List[str] = field(default_factory=list)
    """Header/banner lines shown above the list — bi_python used this for
    "No bins yet." / "No items in this bin." empty-state messaging."""


@dataclass
class FormSpec(ScreenSpec):
    fields: List[FieldSpec] = field(default_factory=list)
    submit_label: str = "Save"
