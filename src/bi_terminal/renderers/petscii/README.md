# Testing the PETSCII door with a real client

`bi_terminal`'s PETSCII renderer talks over stdin/stdout (matching
Synchronet's real "Standard I/O" door invocation — see `door32.py`'s stub
for the eventual Socket/DOOR32.SYS alternative, not built yet). A real
PETSCII client (SyncTERM, VICE, or a real C64) can't attach to a process's
stdin/stdout directly — it needs a TCP socket. A tiny bridge connects the
two with no `bi_terminal` code changes, spawning a fresh process per
connection — genuinely the same shape as how Synchronet itself invokes a
Standard I/O door, just without the rest of the BBS around it.

## Run the bridge

**Verified working end-to-end** (real TCP connection, real backend call,
byte-for-byte correct PETSCII output confirmed via `xxd`) using
`netcat-traditional`, which is what's actually installed here (`socat`
isn't, and isn't needed):

```bash
cd /home/daniel/Binventory/bi_terminal
nc.traditional -l -p 6502 -e scripts/run_petscii_door.sh
```

(`nc -e` only accepts a single executable path, not a full command with
arguments — that's what `scripts/run_petscii_door.sh` is for: it just `cd`s
to the repo and execs `python3 -m bi_terminal.entry_petscii` with
`PYTHONPATH` set. 6502 is a nod to the C64's CPU; any free port works.)

**Caveat:** `nc.traditional -l` handles one connection and then exits —
fine for manual testing (just re-run the command for each session), but if
you want it to keep listening for repeat connections without re-running by
hand, wrap it in a loop:
```bash
while true; do nc.traditional -l -p 6502 -e scripts/run_petscii_door.sh; done
```
Or install `socat` (`sudo apt install socat`) for true concurrent
multi-connection handling:
```bash
socat TCP-LISTEN:6502,reuseaddr,fork EXEC:"scripts/run_petscii_door.sh"
```

Find this machine's LAN IP for the client to connect to:

```bash
hostname -I | awk '{print $1}'
```

## Point a client at it

- **SyncTERM** (Mac Studio): add a new connection, telnet, host = this
  machine's IP, port `6502`, terminal type PETSCII/CG.
- **VICE** (Sasquatch, once installed): most VICE machines can dial out via
  their modem/RS-232 emulation to a `host:port`, or use VICE's own
  Ethernet/`rs232` netplay-style options if configured for direct TCP —
  consult VICE's own docs for the exact setting name in the version
  installed, since this varies by VICE release.
- **Real C64** with a WiFi modem / Ethernet cart pointed at the same
  `host:port` also works — the door doesn't know or care how the bytes
  arrived, only that they're valid PETSCII either direction.

## What this does and doesn't verify

Does: real character-set switching, real control-code rendering, real
input parsing against an actual PETSCII-aware client — the things this
project's own research (see the plan that produced this renderer) couldn't
verify without one, especially the Escape-key byte assumption
(`renderers/petscii/io.py`'s `ESCAPE_BYTE`, currently `0x1B`, flagged there
as unverified).

Doesn't: multi-user concurrency (unless you use the `socat` variant above),
real Synchronet integration (SCFG door setup, DOOR32.SYS drop files), or
anything image-related (this renderer's `show_image` is a deliberate
no-op — see `renderer.py`'s module docstring).
