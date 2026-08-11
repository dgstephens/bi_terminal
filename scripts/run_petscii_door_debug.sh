#!/bin/sh
# Temporary diagnostic wrapper — point SCFG's PETSCII door "Command Line"
# at this script INSTEAD of the normal bi-terminal-petscii binary for one
# real BBS test session, then switch it back.
#
# Logs a startup marker (with environment info) to ~/petscii_startup.log
# BEFORE attempting to exec anything -- if the door "immediately exits"
# when Synchronet invokes it, this tells us whether Synchronet even
# successfully ran this script at all, with what environment/arguments,
# before we ever get to bi-terminal-petscii itself. Separate from
# BI_TERMINAL_PETSCII_DEBUG_LOG (~/petscii_debug.log), which only starts
# logging once the Python app is far enough along to read keys.
{
  echo "=== $(date -Iseconds) ==="
  echo "invoked as: $0 $*"
  echo "whoami: $(whoami)"
  echo "HOME: $HOME"
  echo "PWD: $PWD"
  echo "PATH: $PATH"
  echo "stdin is a tty: $(test -t 0 && echo yes || echo no)"
  echo "stdout is a tty: $(test -t 1 && echo yes || echo no)"
  echo "python3 resolves to: $(command -v python3 2>&1)"
  echo "binary exists and is executable: $(test -x /home/daniel/.local/bin/bi-terminal-petscii && echo yes || echo NO)"
} >> "$HOME/petscii_startup.log" 2>&1

export BI_TERMINAL_PETSCII_DEBUG_LOG="$HOME/petscii_debug.log"
exec /home/daniel/.local/bin/bi-terminal-petscii
