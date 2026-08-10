"""Local config persistence — ported verbatim from bi_python/config.py.

Flat JSON at ~/.binventory/config.json (token, userId, email, image_mode,
base_url).

**Only the Textual renderer actually persists identity here.** load()/
save()/clear_auth() are used for that — a single local user, on their own
machine, wants their login to survive across runs. Door renderers (ANSI/
PETSCII/ATASCII) must NEVER touch identity in this file at all — see
door_cfg() below and AppDriver's persist_config docstring for why: this
file has no concept of "which caller," so on a BBS serving multiple
callers from the same OS account, whoever logged in most recently would
otherwise silently become whoever connects next. This was a real,
live-reported bug (2026-08-10), not a hypothetical -- the original design
note here used to say the opposite ("Textual and a locally-run door
process on the same box should see the same logged-in session"), which is
exactly the assumption that caused it.
"""

import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".binventory"
CONFIG_FILE = CONFIG_DIR / "config.json"
DEFAULT_URL = "https://bin-inventory-backend-a5156630dc89.herokuapp.com/api"


def load() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"base_url": DEFAULT_URL}


def door_cfg() -> dict:
    """For door renderers (ANSI/PETSCII/ATASCII) only -- see AppDriver's
    persist_config docstring for the full story. Real, live-reported bug
    (2026-08-10): every renderer sharing one ~/.binventory/config.json
    meant one BBS caller's login leaked straight to the next caller's
    connection. This is the other half of the fix that a persist_config
    flag alone doesn't cover: `load()` reads token/userId/email back off
    disk too, so a door that called `load()` and just skipped *saving*
    would still auto-login as whoever was last saved there.

    door_cfg() never reads or writes identity at all -- every connection
    starts fully logged out, forcing a fresh login every time, which is the
    only correct behavior for a shared multi-caller BBS account. The one
    thing it *does* read from the file is `base_url` -- non-sensitive
    connection config a sysop might genuinely want to point at a
    non-default backend, not caller identity, so there's no leak risk in
    reading just that one key."""
    base_url = DEFAULT_URL
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                base_url = json.load(f).get("base_url", DEFAULT_URL)
        except Exception:
            pass
    return {"base_url": base_url, "image_mode": "none"}


def save(cfg: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)
    # This file holds a bearer auth token in plaintext — restrict to
    # owner-only. Re-applied on every save since a plain open(..., "w") uses
    # the process umask, which can leave it group/world-readable.
    os.chmod(CONFIG_FILE, 0o600)


def clear_auth(cfg: dict, persist: bool = True) -> dict:
    for key in ("token", "userId", "email"):
        cfg.pop(key, None)
    if persist:
        save(cfg)
    return cfg
