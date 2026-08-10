"""The Renderer contract every renderer (Textual, ANSI/PETSCII/ATASCII doors)
implements against the same specs.

Sync, not async, at this boundary. Textual needs async because its own event
loop demands it (bi_python wrapped every API call in `asyncio.to_thread` for
exactly this reason); a stdio DOOR32.SYS door process has no such requirement
— a plain blocking read/write loop is correct and simpler there. Sync is the
lower common denominator: the Textual renderer bridges sync-Protocol-call to
its internal async screen stack itself (an implementation detail fully
contained in renderers/textual/, invisible to core/specs) rather than forcing
async onto three door renderers that don't need it. This bridging approach is
the one nontrivial technical risk in the whole project — see the README's
"tracer bullet" step, meant to prove it cheaply before the full Textual
renderer is built.
"""

from enum import Enum
from typing import Any, List, Protocol, Union

from ..specs.fields import (
    ActionMenuSpec,
    ConfirmSpec,
    FormSpec,
    ListPickerSpec,
    TextPromptSpec,
)


class ImageCapability(Enum):
    NONE = "none"
    """No image rendering at all — fastest, works everywhere."""
    ANSI_PIXELS = "ansi"
    """rich-pixels-style half-block color art. Textual (user setting) and,
    eventually, the generic ANSI door (fixed) share this — see
    renderers/_shared_ansi_art.py, reserved now, populated when the Textual
    renderer is rewritten so the ANSI door can import the same conversion
    code instead of it being extracted later."""
    ASCII_ART = "ascii"
    """ascii_magic-style monochrome art. Same sharing note as above."""
    PETSCII_GRAPHICS = "petscii"
    """C64 charset/hi-res graphics conversion — not yet implemented, reserved
    so renderers/petscii/renderer.py's stub has a real capability value to
    declare once it exists."""
    ATASCII_GRAPHICS = "atascii"
    """Atari 8-bit ANTIC/GTIA graphics conversion — not yet implemented,
    same status as PETSCII_GRAPHICS above."""


class Renderer(Protocol):
    """Every renderer method's return type documents which sentinel(s) it can
    produce — see specs.base.CANCELLED / specs.base.EMPTY_SUBMIT."""

    image_capability: ImageCapability

    def show_action_menu(self, spec: ActionMenuSpec) -> Any:
        """Returns whatever the chosen ActionItem's `value` was, or a
        core.flow.GlobalNavigate if the user pressed a global-nav digit
        (only possible when spec.nav_enabled), or specs.base.CANCELLED on
        Esc/Ctrl+C."""
        ...

    def show_list_picker(self, spec: ListPickerSpec) -> Any:
        """Returns the chosen Choice's `value`, or specs.base.CANCELLED."""
        ...

    def show_form(self, spec: FormSpec) -> Union[dict, Any]:
        """Returns {field.name: value, ...} for every field in spec.fields,
        or specs.base.CANCELLED. Never partially-filled — a renderer's
        form-runner must apply every field's validator (and re-prompt/refuse
        to dismiss on failure) before returning a dict, matching bi_python's
        "invalid submit stays on the form" behavior."""
        ...

    def show_confirm(self, spec: ConfirmSpec) -> bool:
        """Returns True/False; no cancelled state — Esc resolves to
        spec.default, matching bi_python's ConfirmScreen."""
        ...

    def show_text_prompt(self, spec: TextPromptSpec) -> Union[str, Any]:
        """Returns the entered string, specs.base.CANCELLED on Esc, or
        specs.base.EMPTY_SUBMIT on a deliberate blank Enter when
        spec.distinguish_empty_submit is True."""
        ...

    def show_image(self, urls: List[str], start_index: int = 0) -> None:
        """Displays image(s) at `urls`, starting at `start_index`, with
        prev/next cycling and wraparound — bi_python's ImagePreviewScreen
        behavior, one call per renderer's own idiom (e.g. arrow keys for
        Textual/ANSI; a single-key cycle may suit PETSCII/ATASCII better,
        given inconsistent arrow-key support across BBS terminal emulation —
        an open design question for that phase, not resolved here). Renders
        according to `self.image_capability`; a renderer with NONE should
        make this a no-op rather than erroring, so callers don't need to
        branch on capability before calling it — but "no-op" means no
        rendering, not necessarily zero user feedback. A NONE renderer
        SHOULD still `self.notify(...)` that images aren't supported here
        (a real, live-reported bug fixed 2026-08-10: a totally silent no-op
        was indistinguishable from the keypress just not working at all)."""
        ...

    def notify(self, message: str, severity: str = "information") -> None:
        """A transient status message — bi_python's toast notifications.
        `severity` is one of "information"/"warning"/"error"."""
        ...
