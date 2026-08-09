"""Console-script entry point: `bi-terminal-petscii`. See renderers/petscii/renderer.py."""

from .renderers.petscii.renderer import PetsciiRenderer


def main() -> None:
    PetsciiRenderer().show_action_menu(None)  # raises NotImplementedError


if __name__ == "__main__":
    main()
