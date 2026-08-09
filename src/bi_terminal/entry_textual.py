"""Console-script entry point: `bi-terminal-textual`.

Tracer-bullet increment (README "Sequencing", step 2): runs
BiTerminalTextualApp, which drives exactly one screen (the main menu) through
TextualRenderer to prove the sync-Renderer/async-Textual bridge. Not yet the
full app — see renderers/textual/app.py's docstring.
"""

from .renderers.textual.app import BiTerminalTextualApp


def main() -> None:
    BiTerminalTextualApp().run()


if __name__ == "__main__":
    main()
