"""Every spec builder in specs/forms.py and specs/menus.py, called once with
minimal representative data, must import cleanly and produce the right spec
type. This exists specifically because test_flow_graph.py only exercises
menus.py (ActionMenuSpec/ListPickerSpec builders) — forms.py's FormSpec
builders had no coverage at all and a real import bug (FormSpec imported
from the wrong module) slipped through until caught by manual verification.
Cheap, deliberate belt-and-suspenders so that class of bug can't hide again.
"""

from bi_terminal.specs import forms, menus
from bi_terminal.specs.fields import ActionMenuSpec, FormSpec, ListPickerSpec

BIN = {
    "id": "b1",
    "binName": "Shelf A",
    "description": "",
    "location": "",
    "type": "",
    "public": False,
    "items": [],
    "image": "https://example.com/bin.png",
    "sharedWith": ["a@example.com"],
}
ITEM = {
    "id": "i1",
    "item": "Widget",
    "binId": "b1",
    "prevBin": "b0",
    "images": ["https://example.com/item.png"],
    "image": "",
    "description": "",
    "type": "",
    "quantity": "3",
    "manufacturer": "",
    "serialNumber": "",
}
USER = {"name": "Daniel", "email": "d@example.com", "about": "", "showOnUsersPage": False, "image": ""}


def test_bin_form_spec_new_and_edit():
    assert isinstance(forms.bin_form_spec(), FormSpec)
    edit_spec = forms.bin_form_spec(existing=BIN)
    assert isinstance(edit_spec, FormSpec)
    field_names = {f.name for f in edit_spec.fields}
    assert {"bin_name", "description", "location", "bin_type", "public", "sw_emails"} <= field_names
    # existing has an image -> ImageManagerField should be present
    assert "current_image" in field_names


def test_item_form_spec_new_and_edit():
    assert isinstance(forms.item_form_spec(bins=[BIN]), FormSpec)
    edit_spec = forms.item_form_spec(bins=[BIN], existing=ITEM)
    field_names = {f.name for f in edit_spec.fields}
    assert {"item", "bin_id", "description", "story"} <= field_names
    assert "existing_images" in field_names  # ITEM has images


def test_item_form_spec_survives_explicit_none_fields():
    """Real, live-reported crash (2026-08-12), captured from Synchronet's
    own sbbs.log: editing a real item crashed the whole door process --
    TypeError: 'NoneType' object is not iterable, in ansi/io.py's
    read_line()'s `buf = list(initial)`. Root cause: `existing.get(key, "")`
    only falls back to "" when the KEY IS MISSING, not when it's present
    with an explicit None -- routine for a MongoDB-backed API's
    never-filled-in fields (a real item's purchaseDate stored as literal
    `null`). The existing ITEM fixture above never had this shape (its
    optional fields are either "" or simply absent), which is exactly why
    this slipped through -- this test's fixture has EXPLICIT Nones,
    matching what actually crashed."""
    item_with_nulls = {
        "id": "i1",
        "item": "Widget",
        "binId": "b1",
        "description": None,
        "story": None,
        "type": None,
        "quantity": None,
        "purchaseDate": None,
        "purchasedFrom": None,
        "manufacturer": None,
        "dateOfManufacture": None,
        "serialNumber": None,
        "purchasePrice": None,
        "images": [],
    }
    spec = forms.item_form_spec(bins=[BIN], existing=item_with_nulls)  # must not raise
    for f in spec.fields:
        if hasattr(f, "default"):
            assert f.default is not None
            assert isinstance(f.default, str)


def test_bin_form_spec_survives_explicit_none_fields():
    """Same bug, same fix, bin form -- see
    test_item_form_spec_survives_explicit_none_fields for the full story.
    sharedWith is a list field with the identical None-vs-missing bug
    (existing.get("sharedWith", []) would have crashed " ".join(None))."""
    bin_with_nulls = {
        "id": "b1",
        "binName": "Shelf A",
        "description": None,
        "location": None,
        "type": None,
        "sharedWith": None,
        "public": None,
    }
    spec = forms.bin_form_spec(existing=bin_with_nulls)  # must not raise
    for f in spec.fields:
        if hasattr(f, "default"):
            assert f.default is not None


def test_profile_form_spec_survives_explicit_none_fields():
    """Same bug, same fix, profile form."""
    user_with_nulls = {"name": None, "email": None, "about": None, "showOnUsersPage": None}
    spec = forms.profile_form_spec(user_with_nulls)  # must not raise
    for f in spec.fields:
        if hasattr(f, "default"):
            assert f.default is not None


def test_profile_form_spec():
    spec = forms.profile_form_spec(USER)
    assert isinstance(spec, FormSpec)
    assert {f.name for f in spec.fields} == {
        "name",
        "email",
        "about",
        "show_on_users_page",
        "password",
        "image_path",
    }


def test_login_signup_form_specs():
    # search_form_spec() was removed (2026-08-09): search is a TextPromptSpec
    # built directly in driver.py's _search_menu() now, not a one-field
    # FormSpec -- see driver.py's comment there for why (Ctrl+S-to-submit
    # was a real regression; Enter must submit a search, matching every
    # renderer's text-prompt contract).
    assert isinstance(forms.login_form_spec(), FormSpec)
    assert isinstance(forms.signup_form_spec(), FormSpec)


def test_all_menu_spec_builders_produce_expected_types():
    assert isinstance(menus.login_choice_spec(), ActionMenuSpec)
    assert isinstance(menus.main_menu_spec("5"), ActionMenuSpec)
    assert isinstance(menus.my_bins_spec([BIN]), ListPickerSpec)
    assert isinstance(menus.bin_detail_menu_spec(BIN), ActionMenuSpec)
    assert isinstance(menus.items_in_bin_spec([ITEM], BIN), ListPickerSpec)
    assert isinstance(menus.all_items_spec([ITEM]), ListPickerSpec)
    assert isinstance(menus.item_detail_menu_spec(ITEM), ActionMenuSpec)
    assert isinstance(menus.search_results_spec([ITEM], "widget"), ListPickerSpec)
    assert isinstance(menus.shared_bins_spec([BIN]), ListPickerSpec)
    assert isinstance(menus.shared_bin_items_spec([ITEM], BIN), ListPickerSpec)
    assert isinstance(menus.profile_menu_spec(USER), ActionMenuSpec)
    assert isinstance(menus.settings_menu_spec("none"), ActionMenuSpec)


def test_empty_list_builders_include_extra_lines_message():
    assert menus.my_bins_spec([]).extra_lines == ["You have no bins yet."]
    assert menus.all_items_spec([]).extra_lines == ["You have no items yet."]
    assert menus.items_in_bin_spec([], BIN).extra_lines == ["No items in this bin."]
    assert menus.shared_bins_spec([]).extra_lines == ["No bins have been shared with you."]
