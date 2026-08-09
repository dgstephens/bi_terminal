"""Action-menu and list-picker spec builders — one function per menu/list
screen in bi_python's app.py flow graph. Each takes plain already-fetched
data (never a live API client) and returns an ActionMenuSpec or
ListPickerSpec.

Action/choice VALUES here are deliberately the same symbolic tags used in
core.flow.FLOW_GRAPH's edges (e.g. "open"/"new"/"back", or a bare dest string
like "bins"/"new_bin") — tests/specs/test_flow_graph.py cross-checks the two
so a spec can never emit an action nothing in the flow graph handles.

Checked field-by-field, shortcut-by-shortcut against bi_python/app.py during
the full Textual-renderer-port increment — this superseded an earlier,
abbreviated pass from the foundation increment that had gotten several
details wrong (New Bin/New Item shortcuts swapped, "Back" using a
non-functional "escape" pseudo-shortcut instead of a real key, several
detail fields and list-row metadata fields missing entirely). Fixed here.
"""

from typing import List, Optional, Tuple

from ..core.models import bin_name_from_item, field_line, fmt_date, item_images, prev_bin_name_from_item
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


def _yes_no(value) -> str:
    return "Yes" if value else "No"


# ── Pre-auth ─────────────────────────────────────────────────────────────


def login_choice_spec() -> ActionMenuSpec:
    """bi_python's login_flow() top-level choice. nav_enabled=False — global
    nav is meaningless before authentication."""
    return ActionMenuSpec(
        title="Binventory",
        prompt="Personal inventory management",
        items=[
            ActionItem("Login", "l", "login"),
            ActionItem("Sign Up", "s", "signup"),
            ActionItem(separator=True),
            ActionItem("Exit", "x", "exit"),
        ],
        nav_enabled=False,
    )


# ── Main ─────────────────────────────────────────────────────────────────


def main_menu_spec(item_count, email: str = "") -> ActionMenuSpec:
    """bi_python's main_dispatch(). `item_count` is a str (the fetched count,
    or "?" if core.policy.fetch_list-style fetch failed — main_dispatch
    tolerates that fetch failing without aborting the whole menu). Shortcuts
    match bi_python exactly: New Bin is 'w', New Item is 'n' (easy to
    transpose by mistake — confirmed against source). nav_enabled defaults
    to True (not overridden here) — matching bi_python exactly: main_dispatch
    goes through the same show_action_menu() wrapper as every other menu, so
    digit presses on the main menu ARE live there too, just a harmless
    self-jump (nothing to actually navigate to from where you already are)."""
    return ActionMenuSpec(
        title=f"Bin Inventory — {item_count} items",
        prompt=f"User: {email}" if email else "",
        items=[
            ActionItem("My Bins", "b", "bins"),
            ActionItem("New Bin", "w", "new_bin"),
            ActionItem("My Items", "i", "items"),
            ActionItem("New Item", "n", "new_item"),
            ActionItem(separator=True),
            ActionItem("Search Items", "s", "search"),
            ActionItem("Shared Bins", "h", "shared"),
            ActionItem(separator=True),
            ActionItem("My Profile", "p", "profile"),
            ActionItem("Settings", "t", "settings"),
            ActionItem(separator=True),
            ActionItem("Logout", "l", "logout"),
            ActionItem("Exit", "x", "exit"),
        ],
    )


# ── Bins ─────────────────────────────────────────────────────────────────


def _bin_list_name(b: dict, show_type: bool = True) -> str:
    parts = [b["binName"]]
    if b.get("location"):
        parts.append(f"[{b['location']}]")
    if show_type and b.get("type"):
        parts.append(b["type"])
    parts.append(f"({len(b.get('items') or [])} items)")
    return "  ".join(parts)


def my_bins_spec(bins: list) -> ListPickerSpec:
    choices = [Choice(_bin_list_name(b), ("open", b)) for b in bins]
    choices.append(Choice("+ New Bin", ("new", None)))
    choices.append(Choice("<- Back", ("back", None)))
    return ListPickerSpec(
        title="My Bins",
        prompt=f"{len(bins)} bin(s) — type to filter, arrows to scroll:",
        choices=choices,
        extra_lines=["You have no bins yet."] if not bins else [],
    )


def bin_detail_menu_spec(b: dict) -> ActionMenuSpec:
    rows = [
        field_line("Name", b.get("binName")),
        field_line("Description", b.get("description")),
        field_line("Location", b.get("location")),
        field_line("Type", b.get("type")),
        field_line("Public", _yes_no(b.get("public"))),
        field_line("Shared with", ", ".join(b.get("sharedWith") or [])),
        field_line("Items", len(b.get("items") or [])),
    ]
    items = [ActionItem("View Items in this Bin", "v", "items")]
    if b.get("image"):
        items.append(ActionItem("View Image", "i", "view_image"))
    items += [
        ActionItem("Edit Bin", "e", "edit"),
        ActionItem("Delete Bin", "d", "delete"),
        ActionItem(separator=True),
        ActionItem("Back", "b", "back"),
    ]
    return ActionMenuSpec(title=b.get("binName", "Bin"), prompt=_detail_prompt(rows), items=items)


def items_in_bin_spec(items: list, bin_data: dict) -> ListPickerSpec:
    choices = [Choice(_item_list_name(it, show_bin=False), ("open", it)) for it in items]
    choices.append(Choice("+ Add Item to this Bin", ("new", None)))
    choices.append(Choice("<- Back", ("back", None)))
    return ListPickerSpec(
        title=f"Items in : {bin_data.get('binName', '')}",
        prompt=f"{len(items)} item(s) — type to filter, arrows to scroll:",
        choices=choices,
        extra_lines=["No items in this bin."] if not items else [],
    )


# ── Items ────────────────────────────────────────────────────────────────


def _item_list_name(it: dict, show_bin: bool = True) -> str:
    parts = [it["item"]]
    if show_bin and bin_name_from_item(it):
        parts.append(f"-> {bin_name_from_item(it)}")
    if it.get("type"):
        parts.append(f"[{it['type']}]")
    if it.get("quantity") is not None:
        parts.append(f"qty:{it['quantity']}")
    return "  ".join(parts)


def all_items_spec(items: list) -> ListPickerSpec:
    choices = [Choice(_item_list_name(it), ("open", it)) for it in items]
    choices.append(Choice("+ New Item", ("new", None)))
    choices.append(Choice("<- Back", ("back", None)))
    return ListPickerSpec(
        title="My Items",
        prompt=f"{len(items)} item(s) — type to filter, arrows to scroll:",
        choices=choices,
        extra_lines=["You have no items yet."] if not items else [],
    )


def item_detail_menu_spec(it: dict) -> ActionMenuSpec:
    images = item_images(it)
    prev_name = prev_bin_name_from_item(it)
    rows = [
        field_line("Name", it.get("item")),
        field_line("Bin", bin_name_from_item(it)),
        field_line("Prev. bin", prev_name),
        field_line("Description", it.get("description")),
        field_line("Story", it.get("story")),
        field_line("Type", it.get("type")),
        field_line("Quantity", it.get("quantity")),
        field_line("Serial #", it.get("serialNumber")),
        field_line("Manufacturer", it.get("manufacturer")),
        field_line("Purch. from", it.get("purchasedFrom")),
        field_line("Purch. date", fmt_date(it.get("purchaseDate"))),
        field_line("Price", it.get("purchasePrice")),
        field_line("Mfr. date", fmt_date(it.get("dateOfManufacture"))),
        field_line("Images", f"{len(images)} image(s)"),
    ]
    items = [ActionItem("Edit Item", "e", "edit"), ActionItem("Delete Item", "d", "delete")]
    if images:
        items.append(ActionItem("View Image(s)", "v", "view_image"))
    if it.get("prevBin"):
        items.append(
            ActionItem(f"Move back to '{prev_name or 'previous bin'}'", "m", "move_prev")
        )
    items += [ActionItem(separator=True), ActionItem("Back", "b", "back")]
    return ActionMenuSpec(title=it.get("item", "Item"), prompt=_detail_prompt(rows), items=items)


# ── Search ───────────────────────────────────────────────────────────────


def search_results_spec(items: list, query: str) -> ListPickerSpec:
    """Only shown when len(items) > 1 — bi_python's search_menu() bypasses
    this entirely and opens the single result directly when there's exactly
    one match (see core.flow.FLOW_GRAPH's "open_single" edge), to avoid a
    reflexive-double-Enter race bi_python hit and fixed the same way."""
    choices = [Choice(_item_list_name(it), ("open", it)) for it in items]
    choices.append(Choice("<- New Search", ("back", None)))
    return ListPickerSpec(
        title=f"Search : {query}",
        prompt="Select item to open, or choose New Search:",
        choices=choices,
        extra_lines=[f"{len(items)} result(s)"],
    )


# ── Shared ───────────────────────────────────────────────────────────────


def shared_bins_spec(bins: list) -> ListPickerSpec:
    """Only called by the app driver when `bins` is non-empty — bi_python's
    shared_bins_menu() notifies+returns immediately without ever showing a
    picker when there's nothing shared (no "+ New" affordance makes sense
    for shared content, unlike My Bins/My Items), so this builder's own
    `extra_lines` empty-state message is a defensive fallback, not the
    actual empty-state UX (that lives in the driver)."""
    choices = [Choice(_bin_list_name(b, show_type=False), ("open", b)) for b in bins]
    choices.append(Choice("<- Back", ("back", None)))
    return ListPickerSpec(
        title="Shared Bins",
        prompt=f"{len(bins)} shared bin(s):",
        choices=choices,
        extra_lines=["No bins have been shared with you."] if not bins else [],
    )


def shared_bin_items_spec(items: list, bin_data: dict) -> ListPickerSpec:
    """Only called by the app driver when `items` is non-empty — see
    shared_bins_spec's docstring for why."""
    choices = [
        Choice(it["item"] + (f"  [{it['type']}]" if it.get("type") else ""), ("open", it))
        for it in items
    ]
    choices.append(Choice("<- Back", ("back", None)))
    return ListPickerSpec(
        title=f"Shared : {bin_data.get('binName', '')}",
        prompt=f"{len(items)} item(s):",
        choices=choices,
        extra_lines=[f"No items in '{bin_data.get('binName', '')}'."] if not items else [],
    )


# ── Profile / Settings ───────────────────────────────────────────────────


def profile_menu_spec(user: dict) -> ActionMenuSpec:
    rows = [
        field_line("Name", user.get("name")),
        field_line("Email", user.get("email")),
        field_line("About", user.get("about")),
        field_line("On users page", _yes_no(user.get("showOnUsersPage"))),
        field_line("Bins", len(user.get("bins") or [])),
        field_line("Items", len(user.get("items") or [])),
    ]
    items = []
    if user.get("image"):
        items.append(ActionItem("View Image", "i", "view_image"))
    items += [
        ActionItem("Edit Profile", "e", "edit"),
        ActionItem(separator=True),
        ActionItem("Back", "b", "back"),
    ]
    return ActionMenuSpec(title="My Profile", prompt=_detail_prompt(rows), items=items)


def settings_menu_spec(current_image_mode: str) -> ActionMenuSpec:
    return ActionMenuSpec(
        title="Settings",
        prompt=f"Image mode: {current_image_mode}",
        items=[
            ActionItem("No images  — fastest, works everywhere", "n", "none"),
            ActionItem("ANSI color blocks  — pixel-art, color terminal", "a", "ansi"),
            ActionItem("ASCII art  — monochrome, works everywhere", "s", "ascii"),
            ActionItem(separator=True),
            ActionItem("Back (no change)", "b", "back"),
        ],
    )
