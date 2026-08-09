"""Generic ANSI/BBS door renderer — STUB.

Not built yet (see README "Sequencing", step 4 — after the Textual renderer
reaches parity and proves the spec is complete). This class exists purely so
the four-entry-point project structure is real and importable today: every
method of the Renderer protocol is present and raises NotImplementedError
explicitly, rather than the module simply not existing, so a caller gets a
clear "not built yet" error instead of an ImportError or a silent no-op.

When built: stdio or DOOR32.SYS-based (see door32.py stub), ~80x24, 16-color
CSI escapes, no mouse. Text-only first; image rendering (ImageCapability.
ANSI_PIXELS / ASCII_ART) comes later, reusing
renderers/_shared_ansi_art.py once the Textual renderer rewrite populates it.
"""

from typing import Any, List, Union

from ...specs.fields import ActionMenuSpec, ConfirmSpec, FormSpec, ListPickerSpec, TextPromptSpec
from ..base import ImageCapability


class AnsiRenderer:
    image_capability = ImageCapability.NONE

    def show_action_menu(self, spec: ActionMenuSpec) -> Any:
        raise NotImplementedError("ANSI door renderer not yet built — see README Sequencing")

    def show_list_picker(self, spec: ListPickerSpec) -> Any:
        raise NotImplementedError("ANSI door renderer not yet built — see README Sequencing")

    def show_form(self, spec: FormSpec) -> Union[dict, Any]:
        raise NotImplementedError("ANSI door renderer not yet built — see README Sequencing")

    def show_confirm(self, spec: ConfirmSpec) -> bool:
        raise NotImplementedError("ANSI door renderer not yet built — see README Sequencing")

    def show_text_prompt(self, spec: TextPromptSpec) -> Union[str, Any]:
        raise NotImplementedError("ANSI door renderer not yet built — see README Sequencing")

    def show_image(self, urls: List[str], start_index: int = 0) -> None:
        raise NotImplementedError("ANSI door renderer not yet built — see README Sequencing")

    def notify(self, message: str, severity: str = "information") -> None:
        raise NotImplementedError("ANSI door renderer not yet built — see README Sequencing")
