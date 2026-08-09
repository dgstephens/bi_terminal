from bi_terminal.core.models import (
    bin_id_from_item,
    bin_name_from_item,
    field_line,
    fmt_date,
    item_images,
    prev_bin_id_from_item,
    prev_bin_name_from_item,
    repopulate_item_bin_refs,
)


def test_fmt_date_iso_with_z_suffix():
    assert fmt_date("2026-08-09T12:00:00.000Z") == "2026-08-09"


def test_fmt_date_empty_returns_empty_string():
    assert fmt_date(None) == ""
    assert fmt_date("") == ""


def test_fmt_date_malformed_falls_back_to_slice():
    assert fmt_date("not-a-date-at-all") == "not-a-date"


def test_bin_id_from_item_nested_object():
    assert bin_id_from_item({"binId": {"id": "b1", "binName": "Shelf A"}}) == "b1"


def test_bin_id_from_item_raw_string():
    assert bin_id_from_item({"binId": "b1"}) == "b1"


def test_bin_id_from_item_missing():
    assert bin_id_from_item({}) == ""


def test_bin_name_from_item_raw_string_has_no_name():
    # Confirmed real API behavior: when binId is a raw string (e.g. straight
    # from update_item's response), there's no name available client-side
    # without a bins-list lookup — that's what repopulate_item_bin_refs is for.
    assert bin_name_from_item({"binId": "b1"}) == ""


def test_prev_bin_is_always_a_raw_string_never_nested():
    # Confirmed against real account data: prevBin is NEVER populated as an
    # object by any endpoint, unlike binId.
    assert prev_bin_id_from_item({"prevBin": "b0"}) == "b0"
    assert prev_bin_name_from_item({"prevBin": "b0"}) == ""


def test_item_images_prefers_images_array():
    assert item_images({"images": ["a.png", "b.png"], "image": "legacy.png"}) == [
        "a.png",
        "b.png",
    ]


def test_item_images_falls_back_to_legacy_single_image():
    assert item_images({"images": [], "image": "legacy.png"}) == ["legacy.png"]


def test_item_images_empty_when_neither_present():
    assert item_images({}) == []


def test_repopulate_item_bin_refs_fills_in_raw_ids():
    bins = [{"id": "b1", "binName": "Shelf A"}, {"id": "b0", "binName": "Old Shelf"}]
    item = {"binId": "b1", "prevBin": "b0"}
    result = repopulate_item_bin_refs(item, bins)
    assert result["binId"] == {"id": "b1", "binName": "Shelf A"}
    assert result["prevBin"] == {"id": "b0", "binName": "Old Shelf"}


def test_repopulate_item_bin_refs_leaves_already_nested_objects_alone():
    bins = [{"id": "b1", "binName": "Shelf A"}]
    item = {"binId": {"id": "b1", "binName": "Shelf A (stale)"}}
    result = repopulate_item_bin_refs(item, bins)
    assert result["binId"]["binName"] == "Shelf A (stale)"


def test_repopulate_item_bin_refs_unknown_id_left_as_raw_string():
    result = repopulate_item_bin_refs({"binId": "does-not-exist"}, [])
    assert result["binId"] == "does-not-exist"


def test_field_line_returns_structured_pair_not_formatted_string():
    assert field_line("Name", "Widget") == ("Name", "Widget")


def test_field_line_uses_em_dash_for_missing_value():
    assert field_line("Description", None) == ("Description", "—")
    assert field_line("Description", "") == ("Description", "—")
