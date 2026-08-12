#!/bin/sh
# Wrapper so `nc -e` (which only accepts a single executable path, no
# arguments) can exec the PETSCII character browser with PYTHONPATH set
# correctly. Same pattern as run_petscii_door.sh -- see
# src/bi_terminal/renderers/petscii/README.md for the full bridge setup,
# and src/bi_terminal/renderers/petscii/char_browser.py for what this tool
# actually does.
cd "$(dirname "$0")/.." || exit 1
PYTHONPATH=src exec python3 -m bi_terminal.entry_petscii_charbrowser
