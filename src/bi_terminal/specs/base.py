"""Base types for the screen/flow spec schema: the dismiss-value contract and
the two abstract dataclasses every concrete field/screen spec extends.

Why dataclasses and not JSON/YAML: door renderers need zero extra deps
(dataclasses are stdlib); several fields carry real callables (validators,
filter functions, dynamic choice-list builders keyed off runtime state like
"the user's current bins list") that a JSON spec would need a side-channel
registry to resolve, while a dataclass just holds the callable directly;
static type-checking across four independent renderer implementations is far
stronger against dataclasses than against duck-typed dicts.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


class _Sentinel:
    """A unique, unpicklable, un-equal-to-anything-but-itself marker.
    `object()` would work too, but a named class gives clearer repr()s in
    test failures and debugger output."""

    def __init__(self, name: str):
        self._name = name

    def __repr__(self) -> str:
        return f"<{self._name}>"


CANCELLED = _Sentinel("CANCELLED")
"""The user backed out (Esc/Ctrl+C) without submitting anything. Every
show_* renderer method that can be cancelled includes this in its return
type. Deliberately NOT `None` — see EMPTY_SUBMIT below for why a two-state
(value-or-None) contract isn't sufficient here."""

EMPTY_SUBMIT = _Sentinel("EMPTY_SUBMIT")
"""The user deliberately submitted an empty value (e.g. pressed Enter on a
blank search box) rather than cancelling. bi_python's search form needed to
tell these apart — Esc goes back to the main menu, a blank Enter re-shows the
search form with a warning — so the dismiss contract has three states, not
two, wherever a spec sets `distinguish_empty_submit=True`."""


@dataclass
class FieldSpec:
    """Base for every field type in specs/fields.py. Not instantiated
    directly (use TextField, SwitchField, etc.)."""

    name: str
    """Dict key this field's value is written under in the form's result."""
    label: str
    required: bool = False
    validator: Optional[Callable[[Any], Optional[str]]] = None
    """validator(value) -> error message, or None if valid. Generalizes
    bi_python's ad-hoc per-form "is bin_name blank? notify+refuse-to-dismiss"
    checks into one mechanism every renderer's form-runner calls uniformly
    for every field, not just the ones that happened to get validation
    hand-written in the original Textual code."""


@dataclass
class ScreenSpec:
    """Marker base for every screen-level spec (ActionMenuSpec, FormSpec,
    ListPickerSpec, ConfirmSpec, TextPromptSpec) in specs/fields.py."""

    title: str = ""
