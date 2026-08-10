#!/bin/sh
# Temporary diagnostic wrapper — point SCFG's PETSCII door "Command Line"
# at this script INSTEAD of the normal bi-terminal-petscii binary for one
# real BBS test session, then switch it back. Logs every raw byte the door
# receives (and what key it resolved to) to the path below, so a real
# Synchronet-mediated connection's actual input bytes can be inspected
# after the fact — see renderers/petscii/io.py's PetsciiKeyReader
# docstring for the bug this is diagnosing (cursor keys + backspace not
# working through Synchronet despite a direct SyncTERM byte capture
# proving the client sends the correct bytes).
export BI_TERMINAL_PETSCII_DEBUG_LOG="$HOME/petscii_debug.log"
exec /home/daniel/.local/bin/bi-terminal-petscii
