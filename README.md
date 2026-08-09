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
    ansi/       generic ANSI door (stub until built)
    petscii/    C64 door (stub until built)
    atascii/    Atari 8-bit door (stub until built)
  entry_*.py    console-script entry points, one per renderer
tests/
  test_layering.py   architectural invariant: no textual import in core/specs
  core/               unit tests for core/ (mocked requests)
  specs/              flow-graph completeness + dismiss-contract tests
  renderers/          renderer smoke tests
```

## Sequencing

1. **Foundation** (this increment) — scaffold, `core/` extracted+consolidated,
   full spec schema for every existing screen, `renderers/base.py` Protocol,
   door renderers present as `NotImplementedError` stubs.
2. **Tracer bullet** — one screen (main menu/login) round-tripping end-to-end
   through the Textual renderer, proving the sync-Protocol/async-Textual
   bridging approach before porting everything.
3. **Full Textual renderer** — port all ~15 screens from `bi_python`, reach
   behavioral parity. Proves the spec is complete.
4. **ANSI door renderer** — stdio/DOOR32.SYS, easiest to test locally (no
   emulator needed).
5. **PETSCII, then ATASCII** — novel charset/graphics conversion work, need
   VICE/Altirra for visual verification.

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
