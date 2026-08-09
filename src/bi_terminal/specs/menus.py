"""Action-menu and list-picker spec builders — one function per menu/list
screen in bi_python's app.py flow graph. Each takes plain already-fetched
data (never a live API client) and returns an ActionMenuSpec or
ListPickerSpec.

Action/choice VALUES here are deliberately the same symbolic tags used in
core.flow.FLOW_GRAPH's edges (e.g. "open"/"new"/"back", or a bare dest string
like "bins"/"new_bin") — tests/specs/test_flow_graph.py cross-checks the two
so a spec can never emit an action nothing in the flow graph handles.
"""

from typing import List, Optional, Tuple

from ..core.models import bin_name_from_item, field_line, item_images, prev_bin_name_from_item
from .fields import ActionItem, ActionMenuSpec, Choice, ListPickerSpec


def _detail_prompt(rows: List[Tuple[str, object]]) -> str:
    """Turns a list of (label, value) pairs — as returned by
    core.models.field_line — into a plain-text banner for an ActionMenuSpec's
    `prompt`. This is the one place the spec layer makes a display decision
    (label: value, one per line) rather than leaving layout entirely to the
    renderer; every renderer target here is a line-oriented terminal, so a
    plain "label: value" line is a safe universal baseline any of them can
    either use as-is or re-lay-out (e.g. column-align, recolor) from the same
    (label, value) pairs by calling core.models.field_line directly instead
    of using this prompt string, if they want finer control."""
    return "\n".join(f"{label}: {value}" for label, value in rows)


# ── Pre-auth ─────────────────────────────────────────────────────────────


def login_choice_spec() -> ActionMenuSpec:
    """bi_python's login_flow() top-level choice. nav_enabled=False — global
    nav is meaningless before authentication."""
    return ActionMenuSpec(
        title="Binventory",
        prompt="Please log in or sign up.",
        items=[
            ActionItem("Login", "l", "login"),
            ActionItem("Sign Up", "s", "signup"),
            ActionItem("Exit", "x", "exit"),
        ],
        nav_enabled=False,
    )


# ── Main ─────────────────────────────────────────────────────────────────


def main_menu_spec(item_count) -> ActionMenuSpec:
    """bi_python's main_dispatch(). `item_count` is a str (the fetched count,
    or "?" if core.policy.fetch_list-style fetch failed — main_dispatch
    tolerates that fetch failing without aborting the whole menu)."""
    return ActionMenuSpec(
        title=f"Bin Inventory — {item_count} items",
        items=[
            ActionItem("My Bins", "b", "bins"),
            ActionItem("New Bin", "n", "new_bin"),
            ActionItem("My Items", "i", "items"),
            ActionItem("New Item", "w", "new_item"),
            ActionItem("Search Items", "s", "search"),
            ActionItem("Shared Bins", "h", "shared"),
            ActionItem("My Profile", "p", "profile"),
            ActionItem("Settings", "t", "settings"),
            ActionItem(separator=True),
            ActionItem("Logout", "l", "logout"),
            ActionItem("Exit", "x", "exit"),
        ],
        nav_enabled=False,
    )


# ── Bins ─────────────────────────────────────────────────────────────────


def my_bins_spec(bins: list) -> ListPickerSpec:
    choices = [Choice(b["binName"], ("open", b)) for b in bins]
    choices.append(Choice("+ New Bin", ("new", None)))
    return ListPickerSpec(
        title="My Bins",
        prompt=f"{len(bins)} bin(s)",
        choices=choices,
        extra_lines=["No bins yet."] if not bins else [],
    )


def bin_detail_menu_spec(b: dict) -> ActionMenuSpec:
    rows = [
        field_line("Name", b.get("binName")),
        field_line("Description", b.get("description")),
        field_line("Location", b.get("location")),
        field_line("Type", b.get("type")),
        field_line("Public", b.get("public")),
        field_line("Items", len(b.get("items") or [])),
    ]
    items = [ActionItem("View Items in this Bin", "v", "items")]
    if b.get("image"):
        items.append(ActionItem("View Image", "i", "view_image"))
    items += [
        ActionItem("Edit Bin", "e", "edit"),
        ActionItem("Delete Bin", "d", "delete"),
        ActionItem(separator=True),
        ActionItem("Back", "escape", "back"),
    ]
    return ActionMenuSpec(title=b.get("binName", "Bin"), prompt=_detail_prompt(rows), items=items)


def items_in_bin_spec(items: list, bin_data: dict) -> ListPickerSpec:
    choices = [Choice(it["item"], ("open", it)) for it in items]
    choices.append(Choice("+ Add Item to this Bin", ("new", None)))
    return ListPickerSpec(
        title=f"Items in {bin_data.get('binName', '')}",
        prompt=f"{len(items)} item(s)",
        choices=choices,
        extra_lines=["No items in this bin."] if not items else [],
    )


# ── Items ────────────────────────────────────────────────────────────────


def all_items_spec(items: list) -> ListPickerSpec:
    choices = [Choice(it["item"], ("open", it)) for it in items]
    choices.append(Choice("+ New Item", ("new", None)))
    return ListPickerSpec(
        title="My Items",
        prompt=f"{len(items)} item(s)",
        choices=choices,
        extra_lines=["You have no items yet."] if not items else [],
    )


def item_detail_menu_spec(it: dict) -> ActionMenuSpec:
    rows = [
        field_line("Name", it.get("item")),
        field_line("Bin", bin_name_from_item(it)),
        field_line("Description", it.get("description")),
        field_line("Type", it.get("type")),
        field_line("Quantity", it.get("quantity")),
        field_line("Manufacturer", it.get("manufacturer")),
        field_line("Serial #", it.get("serialNumber")),
    ]
    items = [ActionItem("Edit Item", "e", "edit"), ActionItem("Delete Item", "d", "delete")]
    if item_images(it):
        items.append(ActionItem("View Image(s)", "v", "view_image"))
    prev_name = prev_bin_name_from_item(it)
    if it.get("prevBin"):
        items.append(
            ActionItem(f"Move back to '{prev_name or 'previous bin'}'", "m", "move_prev")
        )
    items += [ActionItem(separator=True), ActionItem("Back", "escape", "back")]
    return ActionMenuSpec(title=it.get("item", "Item"), prompt=_detail_prompt(rows), items=items)


# ── Search ───────────────────────────────────────────────────────────────


def search_results_spec(items: list, query: str) -> ListPickerSpec:
    """Only shown when len(items) > 1 — bi_python's search_menu() bypasses
    this entirely and opens the single result directly when there's exactly
    one match (see core.flow.FLOW_GRAPH's "open_single" edge), to avoid a
    reflexive-double-Enter race bi_python hit and fixed the same way."""
    choices = [Choice(it["item"], ("open", it)) for it in items]
    choices.append(Choice("<- New Search", ("back", None)))
    return ListPickerSpec(title=f"Search: {query}", prompt=f"{len(items)} result(s)", choices=choices)


# ── Shared ───────────────────────────────────────────────────────────────


def shared_bins_spec(bins: list) -> ListPickerSpec:
    choices = [Choice(b["binName"], ("open", b)) for b in bins]
    return ListPickerSpec(
        title="Shared Bins",
        prompt=f"{len(bins)} bin(s)",
        choices=choices,
        extra_lines=["No bins have been shared with you."] if not bins else [],
    )


def shared_bin_items_spec(items: list, bin_data: dict) -> ListPickerSpec:
    choices = [Choice(it["item"], ("open", it)) for it in items]
    return ListPickerSpec(
        title=f"Items in {bin_data.get('binName', '')}",
        prompt=f"{len(items)} item(s)",
        choices=choices,
        extra_lines=["No items in this bin."] if not items else [],
    )


# ── Profile / Settings ───────────────────────────────────────────────────


def profile_menu_spec(user: dict) -> ActionMenuSpec:
    rows = [
        field_line("Name", user.get("name")),
        field_line("Email", user.get("email")),
        field_line("About", user.get("about")),
        field_line("Show on Users Page", user.get("showOnUsersPage")),
    ]
    items = []
    if user.get("image"):
        items.append(ActionItem("View Image", "i", "view_image"))
    items += [
        ActionItem("Edit Profile", "e", "edit"),
        ActionItem(separator=True),
        ActionItem("Back", "escape", "back"),
    ]
    return ActionMenuSpec(title="My Profile", prompt=_detail_prompt(rows), items=items)


def settings_menu_spec(current_image_mode: str) -> ActionMenuSpec:
    marker = {"none": "", "ansi": "", "ascii": ""}
    marker[current_image_mode] = " (current)"
    return ActionMenuSpec(
        title="Settings",
        prompt="Image display mode:",
        items=[
            ActionItem(f"None{marker['none']}", "n", "none"),
            ActionItem(f"ANSI{marker['ansi']}", "a", "ansi"),
            ActionItem(f"ASCII{marker['ascii']}", "s", "ascii"),
            ActionItem(separator=True),
            ActionItem("Back", "escape", "back"),
        ],
    )
