# Testing the ATASCII door with a real client

Same bridge technique as `renderers/petscii/README.md` (worth reading that
one too — this is the shorter, ATASCII-specific version). `bi_terminal`'s
ATASCII renderer talks over stdin/stdout; a real ATASCII client (SyncTERM,
an Atari emulator like Altirra/Atari800, or a real Atari 8-bit with a
network adapter) needs a TCP socket, so a tiny bridge connects the two with
no `bi_terminal` code changes.

## Run the bridge

**Verified working end-to-end** (real TCP connection, real backend call,
byte-for-byte correct ATASCII output confirmed via `xxd`) using
`netcat-traditional`:

```bash
cd /home/daniel/Binventory/bi_terminal
nc.traditional -l -p 8130 -e scripts/run_atascii_door.sh
```

(8130, the Atari 800's model number; any free port works. `nc -e` only
accepts a single executable path, hence the wrapper script — see
`scripts/run_atascii_door.sh`.)

Same caveats as the PETSCII bridge: `nc.traditional -l` handles one
connection and exits (wrap in `while true; do ...; done` to keep listening,
or install `socat` for true concurrent handling — see
`renderers/petscii/README.md` for the exact commands, identical here with
the port/script swapped).

Find this machine's LAN IP: `hostname -I | awk '{print $1}'`

## Point a client at it

- **SyncTERM**: add a connection, telnet, host = this machine's IP, port
  `8130`, terminal type ATASCII.
- **Altirra / Atari800** (or VICE's Atari-emulation modes, once installed):
  consult the emulator's own docs for its network/modem-emulation setting —
  varies by emulator and version.
- **Real Atari 8-bit** with a network adapter (e.g. FujiNet) pointed at the
  same `host:port` also works.

## What this does and doesn't verify

Does: real control-code rendering, real inverse-video highlighting, real
input parsing against an actual ATASCII-aware client — especially the two
assumptions `renderers/atascii/io.py` flags as unverified without one:
`ESCAPE_BYTE` (27) and `RETURN_BYTE` (155). Higher confidence than the
PETSCII renderer's equivalent flags (both are ATASCII's own named,
documented control codes, not borrowed conventions), but still not
live-tested.

Doesn't: multi-user concurrency (unless using the `socat` variant), real
Synchronet integration, or anything image-related (`show_image` is a
deliberate no-op — see `renderer.py`'s module docstring). Also worth
knowing: Synchronet itself has no documented ATASCII-equivalent to
PETSCII's port-64/128 auto-detection (checked directly) — real deployment
would need a separate self-selected door menu entry, same as PETSCII.
