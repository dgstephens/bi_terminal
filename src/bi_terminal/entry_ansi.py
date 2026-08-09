"""Console-script entry point: `bi-terminal-ansi`. See renderers/ansi/renderer.py."""

from .renderers.ansi.renderer import AnsiRenderer


def main() -> None:
    AnsiRenderer().show_action_menu(None)  # raises NotImplementedError


if __name__ == "__main__":
    main()
