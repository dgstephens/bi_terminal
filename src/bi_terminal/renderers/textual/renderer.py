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
    def __init__(self, app, image_mode: str = "none") -> None:
        self.app = app
        # image_mode is a per-session USER SETTING here (unlike the door
        # renderers, where image_capability will be a fixed hardware fact) —
        # sourced from core.config's "image_mode" key, matching bi_python.
        self.image_mode = image_mode
        self.image_capability = _MODE_TO_CAPABILITY.get(image_mode, ImageCapability.NONE)

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
