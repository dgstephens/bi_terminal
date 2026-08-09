"""Console-script entry point: `bi-terminal-textual`.

Full parity port complete (README "Sequencing", step 3) — this is now the
real app: loads ~/.binventory/config.json, constructs the real API client,
and runs BiTerminalTextualApp exactly like bi_python's binventory.py did.
"""

from .renderers.textual.app import main


if __name__ == "__main__":
    main()
