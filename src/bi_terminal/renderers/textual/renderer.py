"""TextualRenderer — the tracer-bullet's proof that a sync Renderer method
can drive a real Textual App from a worker thread.

Every method here must be called from inside a Textual `run_worker(...,
thread=True)` body — NOT a bare threading.Thread — because push_screen_wait
requires Textual's `active_worker` contextvar to already be set on the
calling OS thread (confirmed by tracing contextvar propagation through
asyncio.run_coroutine_threadsafe in the installed Textual 8.2.8 source; see
the plan that produced this file). `App.call_from_thread` alone does not
establish that context — only Textual's own worker machinery does.
"""

from typing import Any, List, Union

from ...specs.fields import ActionMenuSpec, ConfirmSpec, FormSpec, ListPickerSpec, TextPromptSpec
from ..base import ImageCapability
from .screens import ActionMenuTextualScreen

_NOT_YET = (
    "TextualRenderer.{} not implemented yet — this is the tracer-bullet "
    "increment (show_action_menu + notify only). See README Sequencing, "
    "step 3 (full Textual renderer port)."
)


class TextualRenderer:
    image_capability = ImageCapability.NONE

    def __init__(self, app) -> None:
        self.app = app

    def show_action_menu(self, spec: ActionMenuSpec) -> Any:
        return self.app.call_from_thread(
            self.app.push_screen_wait, ActionMenuTextualScreen(spec)
        )

    def notify(self, message: str, severity: str = "information") -> None:
        self.app.call_from_thread(self.app.notify, message, severity=severity)

    def show_list_picker(self, spec: ListPickerSpec) -> Any:
        raise NotImplementedError(_NOT_YET.format("show_list_picker"))

    def show_form(self, spec: FormSpec) -> Union[dict, Any]:
        raise NotImplementedError(_NOT_YET.format("show_form"))

    def show_confirm(self, spec: ConfirmSpec) -> bool:
        raise NotImplementedError(_NOT_YET.format("show_confirm"))

    def show_text_prompt(self, spec: TextPromptSpec) -> Union[str, Any]:
        raise NotImplementedError(_NOT_YET.format("show_text_prompt"))

    def show_image(self, urls: List[str], start_index: int = 0) -> None:
        raise NotImplementedError(_NOT_YET.format("show_image"))
