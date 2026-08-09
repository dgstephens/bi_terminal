# bi_terminal

Multi-renderer terminal client for [Binventory](https://github.com/dgstephens/bi_python)
(Daniel's workshop-inventory tracker). One shared core + a declarative,
renderer-agnostic screen/flow spec, driven by four renderers:

1. **Textual** — the local, rich TUI (successor to `bi_python`'s app)
2. **ANSI door** — generic 80×24 ANSI/BBS terminal, via Synchronet DOOR32.SYS or stdio
3. **PETSCII door** — Commodore 64, 40-column, native control codes
4. **ATASCII door** — Atari 8-bit, 40-column, its own control-code table

## Why this exists, and why not just "transform the Textual output"

Textual's async/mouse/widget model has no clean transform down to raw
PETSCII/ATASCII control-code streams — different code tables, no ANSI CSI
escapes, different screen geometries (40-column fixed for C64/Atari vs.
Textual's resizable truecolor canvas). Instead, the app is split into:

- **`core/`** — data models, the `BinInventoryAPI` client, business/validation
  logic. Zero rendering-toolkit imports, ever (`requests` only) — enforced by
  `tests/test_layering.py`.
- **`specs/`** — a declarative description of every screen (fields, actions,
  validation), expressed as plain Python dataclasses (not JSON/YAML — several
  fields need embedded callables like validators and dynamic choice-list
  builders, and dataclasses give real type-checking across four independent
  renderer implementations). Depends on `core/` only.
- **`renderers/`** — one implementation of the `Renderer` protocol
  (`renderers/base.py`) per target, each consuming the same specs in its own
  idiom.

Doors in Synchronet can be written in any language including Python, wired via
`Standard` (stdio) or `Socket` (DOOR32.SYS) I/O, configured per-door in SCFG.
DOOR32.SYS's `Emulation` field only distinguishes Ascii/Ansi/Avatar/RIP/
MaxGraphics — there's no PETSCII/ATASCII value, and Synchronet's own Ctrl-A
terminal translation doesn't apply to arbitrary door output — so a door
**cannot auto-detect** PETSCII vs. ATASCII vs. ANSI. The plan is separate door
menu entries so the user self-selects ("Binventory - ANSI" / "- PETSCII" /
"- ATASCII").

## Repo layout

```
src/bi_terminal/
  core/         data models, API client, business logic — no rendering deps
  specs/        declarative screen/flow spec (dataclasses), depends on core only
  renderers/
    base.py     Renderer Protocol + ImageCapability enum
    textual/    the local rich TUI renderer
    ansi/       generic stdio ANSI/BBS door — text-only, working
    petscii/    C64 door (stub until built)
    atascii/    Atari 8-bit door (stub until built)
  entry_*.py    console-script entry points, one per renderer
  driver.py     AppDriver — the shared flow orchestration EVERY renderer's
                app is built from (extracted from renderers/textual/app.py
                once building the ANSI renderer proved it was 100%
                renderer-agnostic); depends only on core/+specs/ and the
                Renderer protocol type, never a concrete renderer
tests/
  test_layering.py   architectural invariant: no textual import in core/specs,
                      no rendering toolkit or concrete renderer import in driver.py
  test_driver.py      AppDriver's flow logic via a scripted fake Renderer
  core/               unit tests for core/ (mocked requests)
  specs/              flow-graph completeness + dismiss-contract tests
  renderers/          per-renderer tests (Textual headless, ANSI pipe-based)
```

## Sequencing

1. **Foundation** — DONE. Scaffold, `core/` extracted+consolidated, full spec
   schema for every existing screen, `renderers/base.py` Protocol, door
   renderers present as `NotImplementedError` stubs.
2. **Tracer bullet** — DONE. One screen (the main menu) round-tripped
   end-to-end through the Textual renderer, proving the sync-Protocol/
   async-Textual bridging approach (a real `call_from_thread` bridge from a
   `run_worker(thread=True)` body) before porting everything.
3. **Full Textual renderer** — DONE. All ~15 screens ported from `bi_python`
   (one generic `FormScreen` consuming any `FormSpec`, not six bespoke
   classes — see `renderers/textual/screens.py`), real image rendering
   (`renderers/_shared_ansi_art.py`, populated as planned), full
   `core.flow`-driven orchestration in `renderers/textual/app.py`. `python3
   -m bi_terminal.entry_textual` is a complete, working app — verified via
   92 headless regression tests (`tests/renderers/`) plus a real run against
   Daniel's live account. Proves the spec is complete. One real bug found
   and fixed along the way (`_edit_item` KeyError on items with no existing
   images); several foundation-increment spec gaps corrected against
   bi_python's actual source (shortcut keys, missing detail fields, missing
   list-row metadata, a missing "<- Back" choice in every list picker).
4. **ANSI door renderer** — DONE (text-only; image capability stays fixed at
   `NONE` this phase, a deliberate limitation). Along the way, extracted
   `driver.py`'s shared `AppDriver` from `renderers/textual/app.py` — it
   turned out ~700 lines of flow orchestration were already 100%
   renderer-agnostic, so the ANSI renderer needed only its own I/O layer
   (`renderers/ansi/io.py` — a `select()`-timeout-peek key reader with a
   pushback buffer, empirically verified against a plain `os.pipe()` before
   being written) and screen-rendering methods
   (`renderers/ansi/renderer.py`), not a second copy of the business logic.
   `python3 -m bi_terminal.entry_ansi` is a complete, working stdio door —
   verified via 172 total tests (94 pre-existing + 78 new) plus a real pty
   run against Daniel's live account (849 real items, real profile data,
   correct scroll-window pagination, clean exit). Stdio (`Standard` I/O
   door mode) only — DOOR32.SYS/Socket-mode wiring stays a stub
   (`renderers/ansi/door32.py`), real follow-up work for actual BBS
   deployment, out of scope for "text-only, local-testable."
5. **PETSCII door renderer** — DONE (text-only; `show_image` stays a no-op
   despite declaring `ImageCapability.PETSCII_GRAPHICS`, same deliberate
   scope limit as ANSI). Genuinely novel protocol, researched from
   authoritative sources before design (sta.c64.org's control-code table,
   c64-wiki's character-set page, Synchronet's own CTerm manual) rather than
   assumed — key findings: PETSCII has **no escape sequences at all**
   (single control bytes only, actually a simpler input model than ANSI's
   CSI parsing), **no absolute cursor positioning** (resolved the same way
   ANSI resolved it: full clear + sequential print, no `move(row,col)`
   needed), and **no lowercase letters until you switch character sets**
   (`CHR$(14)`, sent once at renderer construction). One thing the research
   couldn't settle without a real client: the Escape-key byte
   (`renderers/petscii/io.py`'s `ESCAPE_BYTE = 0x1B`, well-reasoned but
   explicitly flagged unverified) — a `scripts/run_petscii_door.sh` +
   `netcat`/`socat` bridge (`renderers/petscii/README.md`) makes real-client
   verification a zero-setup "point SyncTERM/VICE at this port" moment
   whenever one's available, confirmed working end-to-end against a real
   TCP connection during this increment (byte-for-byte correct PETSCII
   output, real backend data). Also caught and fixed, empirically, a real
   silent-corruption bug before it ever shipped: Python's default `stdout`
   text encoding (UTF-8) double-encodes any control byte above 0x7F, so
   `PetsciiIO` is binary throughout (`sys.stdout.buffer`, never `sys.stdout`
   text mode). 233 total tests passing (172 pre-existing + 61 new) plus a
   real pty-driven run against Daniel's live account.
6. **ATASCII** — next. Its own novel protocol (Atari 8-bit ANTIC/GTIA), same
   pattern as PETSCII: research the real control codes first, build its own
   I/O layer + renderer against the unchanged shared `AppDriver`.

Full design rationale (including the specific bug fixes folded into the core
extraction — a `get_shared_bins` response-key mismatch, inconsistent 404
handling across list endpoints, a typed `ImageFileNotFoundError`, a
shared-bin-items bin-ref bug) lives in the planning session that produced this
repo — see the Syncronet and Claudio/BinInventory project memories if you need
that history.

## Sibling repos

- `bi_backend` — Node/Express/MongoDB/S3 API this all talks to
- `bi_frontend` — React web frontend
- `bi_python` (`/home/daniel/Binventory/bi_python`) — the existing standalone
  Textual TUI this project's Textual renderer supersedes. Left untouched;
  not a dependency of this repo.
