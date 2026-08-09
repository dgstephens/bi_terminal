"""Console-script entry point: `bi-terminal-atascii`. See renderers/atascii/renderer.py."""

from .renderers.atascii.renderer import AtasciiRenderer


def main() -> None:
    AtasciiRenderer().show_action_menu(None)  # raises NotImplementedError


if __name__ == "__main__":
    main()
