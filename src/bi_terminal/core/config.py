"""Local config persistence — ported verbatim from bi_python/config.py.

Flat JSON at ~/.binventory/config.json (token, userId, email, image_mode,
base_url). Shared across renderers on the same machine deliberately — the
Textual renderer and a locally-run door renderer process on the same box
should see the same logged-in session.
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


def save(cfg: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)
    # This file holds a bearer auth token in plaintext — restrict to
    # owner-only. Re-applied on every save since a plain open(..., "w") uses
    # the process umask, which can leave it group/world-readable.
    os.chmod(CONFIG_FILE, 0o600)


def clear_auth(cfg: dict) -> dict:
    for key in ("token", "userId", "email"):
        cfg.pop(key, None)
    save(cfg)
    return cfg
