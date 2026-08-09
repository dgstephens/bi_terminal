"""Commodore 64 PETSCII door renderer — STUB.

Not built yet (see README "Sequencing", step 5 — after ANSI, needs real
charset/graphics conversion work and VICE for visual verification). Every
Renderer protocol method is present and raises NotImplementedError so the
four-entry-point structure is real and importable today; see
renderers/ansi/renderer.py's docstring for the reasoning, identical here.

When built: 40-column, native PETSCII control codes (not ANSI CSI escapes),
image rendering via ImageCapability.PETSCII_GRAPHICS (hi-res/multicolor
charset packing — genuinely new code, not shared with the ANSI door).
"""

from typing import Any, List, Union

from ...specs.fields import ActionMenuSpec, ConfirmSpec, FormSpec, ListPickerSpec, TextPromptSpec
from ..base import ImageCapability


class PetsciiRenderer:
    image_capability = ImageCapability.NONE

    def show_action_menu(self, spec: ActionMenuSpec) -> Any:
        raise NotImplementedError("PETSCII door renderer not yet built — see README Sequencing")

    def show_list_picker(self, spec: ListPickerSpec) -> Any:
        raise NotImplementedError("PETSCII door renderer not yet built — see README Sequencing")

    def show_form(self, spec: FormSpec) -> Union[dict, Any]:
        raise NotImplementedError("PETSCII door renderer not yet built — see README Sequencing")

    def show_confirm(self, spec: ConfirmSpec) -> bool:
        raise NotImplementedError("PETSCII door renderer not yet built — see README Sequencing")

    def show_text_prompt(self, spec: TextPromptSpec) -> Union[str, Any]:
        raise NotImplementedError("PETSCII door renderer not yet built — see README Sequencing")

    def show_image(self, urls: List[str], start_index: int = 0) -> None:
        raise NotImplementedError("PETSCII door renderer not yet built — see README Sequencing")

    def notify(self, message: str, severity: str = "information") -> None:
        raise NotImplementedError("PETSCII door renderer not yet built — see README Sequencing")
