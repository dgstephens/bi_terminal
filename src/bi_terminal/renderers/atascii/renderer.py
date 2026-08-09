"""Atari 8-bit ATASCII door renderer — STUB.

Not built yet (see README "Sequencing", step 5 — alongside PETSCII, needs
real ANTIC/GTIA graphics conversion work and Altirra for visual
verification; order between PETSCII/ATASCII is whichever Daniel has better
local emulator tooling for, decided when that phase starts). Every Renderer
protocol method is present and raises NotImplementedError so the
four-entry-point structure is real and importable today; see
renderers/ansi/renderer.py's docstring for the reasoning, identical here.

When built: 40-column, native ATASCII control codes (its own table, distinct
from both ANSI CSI escapes and PETSCII codes), image rendering via
ImageCapability.ATASCII_GRAPHICS.
"""

from typing import Any, List, Union

from ...specs.fields import ActionMenuSpec, ConfirmSpec, FormSpec, ListPickerSpec, TextPromptSpec
from ..base import ImageCapability


class AtasciiRenderer:
    image_capability = ImageCapability.NONE

    def show_action_menu(self, spec: ActionMenuSpec) -> Any:
        raise NotImplementedError("ATASCII door renderer not yet built — see README Sequencing")

    def show_list_picker(self, spec: ListPickerSpec) -> Any:
        raise NotImplementedError("ATASCII door renderer not yet built — see README Sequencing")

    def show_form(self, spec: FormSpec) -> Union[dict, Any]:
        raise NotImplementedError("ATASCII door renderer not yet built — see README Sequencing")

    def show_confirm(self, spec: ConfirmSpec) -> bool:
        raise NotImplementedError("ATASCII door renderer not yet built — see README Sequencing")

    def show_text_prompt(self, spec: TextPromptSpec) -> Union[str, Any]:
        raise NotImplementedError("ATASCII door renderer not yet built — see README Sequencing")

    def show_image(self, urls: List[str], start_index: int = 0) -> None:
        raise NotImplementedError("ATASCII door renderer not yet built — see README Sequencing")

    def notify(self, message: str, severity: str = "information") -> None:
        raise NotImplementedError("ATASCII door renderer not yet built — see README Sequencing")
