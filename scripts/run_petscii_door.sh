#!/bin/sh
# Wrapper so `nc -e` (which only accepts a single executable path, no
# arguments) can exec the PETSCII door with PYTHONPATH set correctly.
# See src/bi_terminal/renderers/petscii/README.md for the full bridge setup.
cd "$(dirname "$0")/.." || exit 1
PYTHONPATH=src exec python3 -m bi_terminal.entry_petscii
