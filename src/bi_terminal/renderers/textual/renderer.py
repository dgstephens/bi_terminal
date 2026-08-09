"""TextualRenderer — the local/rich renderer, driving a real Textual App
from a worker thread via the sync Renderer protocol.

Every method here must be called from inside a Textual `run_worker(...,
thread=True)` body — NOT a bare threading.Thread — because push_screen_wait
requires Textual's `active_worker` contextvar to already be set on the
calling OS thread (confirmed by tracing contextvar propagation through
asyncio.run_coroutine_threadsafe in the installed Textual 8.2.8 source, in
the tracer-bullet increment that first proved this). `App.call_from_thread`
alone does not establish that context — only Textual's own worker machinery
does.
"""

from typing import Any, List, Union

from ...specs.fields import ActionMenuSpec, ConfirmSpec, FormSpec, ListPickerSpec, TextPromptSpec
from ..base import ImageCapability
from .screens import (
    ActionMenuTextualScreen,
    ConfirmTextualScreen,
    FormScreen,
    ImagePreviewTextualScreen,
    ListPickerTextualScreen,
    TextPromptTextualScreen,
)

_MODE_TO_CAPABILITY = {
    "none": ImageCapability.NONE,
    "ansi": ImageCapability.ANSI_PIXELS,
    "ascii": ImageCapability.ASCII_ART,
}


class TextualRenderer:
    def __init__(self, app) -> None:
        self.app = app

    @property
    def image_mode(self) -> str:
        """Reads app.cfg["image_mode"] FRESH on every access, rather than
        caching it at construction — matching bi_python's own original
        design (it re-read cfg["image_mode"] fresh on every
        ImagePreviewScreen construction). This is also what keeps the
        shared driver.py's _settings_menu fully renderer-agnostic: it only
        ever writes self.cfg["image_mode"] and never needs to reach into
        renderer internals — a real coupling problem in an earlier version
        of this file, fixed during the driver-extraction refactor."""
        return self.app.cfg.get("image_mode", "none")

    @property
    def image_capability(self) -> ImageCapability:
        return _MODE_TO_CAPABILITY.get(self.image_mode, ImageCapability.NONE)

    def show_action_menu(self, spec: ActionMenuSpec) -> Any:
        return self.app.call_from_thread(
            self.app.push_screen_wait, ActionMenuTextualScreen(spec)
        )

    def show_list_picker(self, spec: ListPickerSpec) -> Any:
        return self.app.call_from_thread(
            self.app.push_screen_wait, ListPickerTextualScreen(spec)
        )

    def show_form(self, spec: FormSpec) -> Union[dict, Any]:
        return self.app.call_from_thread(
            self.app.push_screen_wait, FormScreen(spec, image_mode=self.image_mode)
        )

    def show_confirm(self, spec: ConfirmSpec) -> bool:
        return self.app.call_from_thread(
            self.app.push_screen_wait, ConfirmTextualScreen(spec)
        )

    def show_text_prompt(self, spec: TextPromptSpec) -> Union[str, Any]:
        return self.app.call_from_thread(
            self.app.push_screen_wait, TextPromptTextualScreen(spec)
        )

    def show_image(self, urls: List[str], start_index: int = 0) -> None:
        # Deliberately does NOT no-op on ImageCapability.NONE, unlike the
        # generic "NONE means no rendering code exists" contract described
        # in renderers/base.py (which fits a not-yet-built door renderer
        # with no fallback code path at all). This renderer always HAS real
        # rendering code (PIL/rich_pixels/ascii_magic) regardless of the
        # user's ambient image_mode setting — matching bi_python's own
        # ImagePreviewScreen exactly, which explicitly falls back to "ansi"
        # on demand even when the default mode is "none" (image_mode="none"
        # only means "don't fetch images automatically while browsing
        # lists," not "this renderer can't render images at all"). The
        # none->ansi fallback itself lives in ImagePreviewTextualScreen.
        self.app.call_from_thread(
            self.app.push_screen_wait,
            ImagePreviewTextualScreen("Image", urls, self.image_mode, start_index),
        )

    def notify(self, message: str, severity: str = "information") -> None:
        self.app.call_from_thread(self.app.notify, message, severity=severity)
