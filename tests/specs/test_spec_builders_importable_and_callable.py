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


def test_search_login_signup_form_specs():
    assert isinstance(forms.search_form_spec(), FormSpec)
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
    assert menus.my_bins_spec([]).extra_lines == ["No bins yet."]
    assert menus.all_items_spec([]).extra_lines == ["You have no items yet."]
    assert menus.items_in_bin_spec([], BIN).extra_lines == ["No items in this bin."]
    assert menus.shared_bins_spec([]).extra_lines == ["No bins have been shared with you."]
