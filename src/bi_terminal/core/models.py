"""Pure data-normalization and business-rule helpers.

Consolidates what bi_python scattered and duplicated: app.py defined its own
top-level fmt_date/_bin_id_from_item/_bin_name_from_item/
_prev_bin_id_from_item/_prev_bin_name_from_item/_item_images/
_repopulate_item_bin_refs/_field_line, and forms.py separately redefined
_fmt_date/_item_images/_bin_id_from_item. One canonical version of each here;
every renderer imports from this module instead of reimplementing any of it.

No rendering-toolkit imports — see core/__init__.py's layering rule.
"""

from datetime import datetime
from typing import List, Optional, Tuple

# Backend requires bins to always have a non-empty `image` field. Removing a
# bin's image (via the image manager) falls back to this constant rather than
# sending "". Confirmed live against Daniel's real account: several of his
# existing bins already use exactly this URL as their default image.
DEFAULT_BIN_IMAGE_URL = "https://bin-inventory-files.s3.us-east-2.amazonaws.com/DefaultBin.png"


def fmt_date(date_str: Optional[str]) -> str:
    """ISO datetime -> YYYY-MM-DD, tolerating malformed input."""
    if not date_str:
        return ""
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return date_str[:10] if len(date_str) >= 10 else date_str


# ── binId / prevBin shape normalization ─────────────────────────────────────
#
# Item objects embed `binId` and `prevBin` as EITHER a raw ID string OR a
# nested {id, binName} object depending on which endpoint returned them:
# GET list/detail endpoints (get_items_by_user, get_items_by_bin, get_item)
# populate binId as a full object; update_item's response does NOT (raw
# string). `prevBin` is a raw ID string from EVERY endpoint, always — never
# populated as an object anywhere. Confirmed against real account data.

def bin_id_from_item(item: dict) -> str:
    bid = item.get("binId")
    if isinstance(bid, dict):
        return bid.get("id", "")
    return bid or ""


def bin_name_from_item(item: dict) -> str:
    bid = item.get("binId")
    if isinstance(bid, dict):
        return bid.get("binName", "")
    return ""


def prev_bin_id_from_item(item: dict) -> str:
    pb = item.get("prevBin")
    if isinstance(pb, dict):
        return pb.get("id", "")
    return pb or ""


def prev_bin_name_from_item(item: dict) -> str:
    pb = item.get("prevBin")
    if isinstance(pb, dict):
        return pb.get("binName", "")
    return ""


def item_images(item: dict) -> List[str]:
    """Normalizes an item's images: prefer the images[] array, fall back to
    the legacy single `image` string field."""
    imgs = item.get("images") or []
    if not imgs and item.get("image"):
        imgs = [item["image"]]
    return [u for u in imgs if u]


def repopulate_item_bin_refs(item: dict, bins: list) -> dict:
    """update_item's response doesn't populate binId/prevBin as nested
    {id, binName} objects the way the list/get-items endpoints do (prevBin in
    particular is ALWAYS just a raw ID string, from every endpoint). Reconstruct
    them client-side from a `bins` list already in hand (e.g. from
    get_bins_by_user), so a detail view shows names immediately after an edit
    instead of going blank until the next full re-fetch. Mutates and returns
    `item` for convenient chaining, matching bi_python's original call sites."""
    bin_lookup = {b["id"]: b for b in bins}
    bid = item.get("binId")
    if not isinstance(bid, dict) and bid in bin_lookup:
        item["binId"] = bin_lookup[bid]
    pb = item.get("prevBin")
    if pb and not isinstance(pb, dict) and pb in bin_lookup:
        item["prevBin"] = bin_lookup[pb]
    return item


def field_line(label: str, value, missing: str = "—") -> Tuple[str, str]:
    """(label, display_value) for a detail-screen field row.

    Deliberately returns structured data, NOT a formatted/padded string —
    bi_python's original _field_line baked in a fixed column width and Rich
    markup, a display decision that only suits one fixed-width renderer.
    Column alignment/padding differs meaningfully between an 80-column ANSI
    terminal and a 40-column PETSCII/ATASCII screen, so layout is each
    renderer's job. The one thing that IS a cross-renderer policy — what to
    show for an empty/None value — stays here as the `missing` default (an em
    dash, matching bi_python's convention)."""
    v = str(value) if value not in (None, "") else missing
    return (label, v)
