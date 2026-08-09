"""Global navigation signal + the app's screen-flow graph, both as plain data.

bi_python's global-nav mechanism (digit keys 1-4 jump straight to Main/Bins/
Items/Search from anywhere) was implemented as a Python exception
(`NavigateTo`) dismissed by a screen, re-raised by a wrapper, and caught by
the outermost driver loop after unwinding Textual's screen stack — plumbing
that only makes sense because Textual screens are nested coroutine calls on
one async stack. A stdio door renderer has no such stack to unwind; it can
just be `while True: r = dispatch(); if isinstance(r, GlobalNavigate): ...`.
So core only defines the *signal* and the *destination table* — how a given
renderer detects/propagates/handles it is that renderer's own business
(bi_python's exception trick is a legitimate thing for the Textual renderer
to keep doing internally, entirely inside renderers/textual/).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GlobalNavigate:
    """Returned/raised by a renderer when the user pressed a global-nav
    shortcut. `dest` is one of NAV_TARGETS' keys."""

    dest: str


# digit -> (dest key used across specs/flow.py, display label)
NAV_TARGETS = {
    "1": ("main", "Main"),
    "2": ("bins", "Bins"),
    "3": ("items", "Items"),
    "4": ("search", "Search"),
}


# ── Flow graph, as inspectable data ─────────────────────────────────────────
#
# One entry per named screen/menu in the app. Each maps the *symbolic* action
# values a spec for that screen can produce (see specs/menus.py, specs/forms.py
# — e.g. ActionItem.value, or the "open"/"new"/"back" tag half of a list
# picker's Choice.value tuple) to either:
#   - another node name in this graph (a plain string) — navigate there
#   - None — terminal for this node (return to caller / exit / handled inline
#     with no further navigation, e.g. a Delete action that just pops back)
#
# This mirrors bi_python's app.py flow graph (confirmed against source):
# main_dispatch, bins_menu, bin_detail, create_bin/edit_bin, items_in_bin_menu,
# all_items_menu, item_detail, create_item/edit_item, search_menu,
# shared_bins_menu, shared_bin_items_view, profile_menu, edit_profile,
# settings_menu, login_flow.
#
# Dynamic per-instance choices (which bin/item was picked) aren't representable
# here by design — the graph only needs to prove every *symbolic* action a spec
# can emit is handled by something, which is exactly what
# tests/specs/test_flow_graph.py checks (no dangling edges).
FLOW_GRAPH = {
    "login": {
        "login": "main",     # _do_login success
        "signup": "main",    # _do_signup success
        "exit": None,
    },
    "main": {
        "bins": "bins",
        "new_bin": "bin_form",
        "items": "all_items",
        "new_item": "item_form",
        "search": "search",
        "shared": "shared_bins",
        "profile": "profile",
        "settings": "settings",
        "logout": "login",
        "exit": None,
    },
    "bins": {
        "open": "bin_detail",
        "new": "bin_form",
        "back": "main",
    },
    "bin_detail": {
        "items": "items_in_bin",
        "view_image": "bin_detail",   # ImagePreviewScreen, returns here
        "edit": "bin_form",
        "delete": "bins",             # notify + return to My Bins
        "back": "bins",
    },
    "bin_form": {
        # Terminal node: submit -> back to whichever menu opened it (bins,
        # bin_detail, or items_in_bin's "+ Add" shortcut all route here and
        # each returns to its own caller — not modeled as a single edge
        # since the return target depends on entry point, same as bi_python).
        "save": None,
        "cancel": None,
    },
    "items_in_bin": {
        "open": "item_detail",
        "new": "item_form",
        "back": "bin_detail",
    },
    "all_items": {
        "open": "item_detail",
        "new": "item_form",
        "back": "main",
    },
    "item_detail": {
        "edit": "item_form",
        "delete": "all_items",        # notify + return (caller-dependent, see bin_form note)
        "view_image": "item_detail",
        "move_prev": "item_detail",   # re-fetch + stay
        "back": "all_items",
    },
    "item_form": {
        "save": None,
        "cancel": None,
    },
    "search": {
        "submit_empty": "search",     # notify + re-show search form
        "no_results": "search",
        "open_single": "item_detail",  # len(results) == 1 shortcut, bypasses picker
        "open": "item_detail",
        "back": "main",
    },
    "shared_bins": {
        "open": "shared_bin_items",
        "back": "main",
    },
    "shared_bin_items": {
        "open": "item_detail",
        "back": "shared_bins",
    },
    "profile": {
        "view_image": "profile",
        "edit": "profile_form",
        "back": "main",
    },
    "profile_form": {
        "save": None,
        "cancel": None,
    },
    "settings": {
        # Settings is a small fixed choice (unlike the dynamic lists above),
        # so its edges are the literal image_mode values bi_python's Settings
        # menu offers, matching specs.menus.settings_menu_spec's ActionItem
        # values exactly rather than a generic "set_image_mode" tag.
        "none": "settings",
        "ansi": "settings",
        "ascii": "settings",
        "back": "main",
    },
}
