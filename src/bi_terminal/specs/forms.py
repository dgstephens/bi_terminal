"""Form spec builders: one function per bi_python form, each returning a
FormSpec whose submitted-dict shape matches bi_python's original result dict
exactly, so core.api's create_*/update_* call sites don't need to change
shape when a renderer's form-runner unpacks the result.

Every builder takes plain data (dicts/None), never a live API client or
renderer object — specs are pure descriptions, not live UI.
"""

from typing import List, Optional

from ..core.models import item_images
from .fields import (
    Choice,
    ComboFilterSelectField,
    FormSpec,
    ImageManagerField,
    ImagePathField,
    MultiImagePathField,
    PasswordField,
    SwitchField,
    TextAreaField,
    TextField,
)


def _non_blank(label: str):
    def validator(value):
        if not str(value or "").strip():
            return f"{label} is required."
        return None

    return validator


def bin_form_spec(existing: Optional[dict] = None) -> FormSpec:
    """bi_python's _BinFormScreen. Result dict on submit:
    {bin_name, description, location, bin_type, public, sw_emails,
     image_path, current_image}
    consumed by core.api.create_bin (no existing) / update_bin (existing)."""
    existing = existing or {}
    sw_emails = " ".join(existing.get("sharedWith", []))
    fields: List = [
        TextField(
            "bin_name",
            "Bin Name",
            required=True,
            validator=_non_blank("Bin Name"),
            default=existing.get("binName", ""),
        ),
        TextField("description", "Description", default=existing.get("description", "")),
        TextField("location", "Location", default=existing.get("location", "")),
        TextField("bin_type", "Type", default=existing.get("type", "")),
        SwitchField("public", "Public", default=bool(existing.get("public"))),
        TextField("sw_emails", "Shared With (space-separated emails)", default=sw_emails),
    ]
    if existing.get("image"):
        fields.append(
            ImageManagerField("current_image", "Images", images=item_images(existing))
        )
    fields.append(ImagePathField("image_path", "New Image Path"))
    return FormSpec(
        title="Edit Bin" if existing else "New Bin",
        fields=fields,
        submit_label="Save",
    )


def item_form_spec(
    bins: list,
    existing: Optional[dict] = None,
    preselect_bin_id: Optional[str] = None,
) -> FormSpec:
    """bi_python's _ItemFormScreen. Result dict on submit:
    {item, bin_id, description, story, item_type, quantity, purchase_date,
     purchased_from, manufacturer, date_of_manufacture, serial_number,
     purchase_price, existing_images, new_image_paths}
    consumed by core.api.create_item (no existing) / update_item (existing).

    `bins` is the caller's already-fetched list of the user's bins (from
    core.api.get_bins_by_user) — the same list used to build the combo-filter
    choices AND, after submit, to repopulate binId/prevBin via
    core.models.repopulate_item_bin_refs. Initial bin selection prefers the
    item's current bin, then `preselect_bin_id` (e.g. "Add Item to this Bin"
    from Items-in-Bin), then the first bin in the list — matching bi_python."""
    existing = existing or {}
    choices = [Choice(b["binName"], b["id"]) for b in bins]
    current_bin_id = None
    bin_id_field = existing.get("binId")
    if isinstance(bin_id_field, dict):
        current_bin_id = bin_id_field.get("id")
    elif bin_id_field:
        current_bin_id = bin_id_field
    default_bin_id = current_bin_id or preselect_bin_id or (bins[0]["id"] if bins else None)

    def _bin_required(value):
        if not value:
            return "Please select a bin."
        return None

    fields: List = [
        TextField(
            "item",
            "Item Name",
            required=True,
            validator=_non_blank("Item Name"),
            default=existing.get("item", ""),
        ),
        ComboFilterSelectField(
            "bin_id",
            "Bin",
            required=True,
            validator=_bin_required,
            choices=choices,
            default_value=default_bin_id,
        ),
        TextAreaField("description", "Description", default=existing.get("description", "")),
        TextAreaField("story", "Story", default=existing.get("story", "")),
        TextField("item_type", "Type", default=existing.get("type", "")),
        TextField("quantity", "Quantity", default=str(existing.get("quantity", ""))),
        TextField(
            "purchase_date",
            "Purchase Date",
            placeholder="YYYY-MM-DD",
            default=existing.get("purchaseDate", ""),
        ),
        TextField("purchased_from", "Purchased From", default=existing.get("purchasedFrom", "")),
        TextField("manufacturer", "Manufacturer", default=existing.get("manufacturer", "")),
        TextField(
            "date_of_manufacture",
            "Mfg. Date",
            placeholder="YYYY-MM-DD",
            default=existing.get("dateOfManufacture", ""),
        ),
        TextField("serial_number", "Serial Number", default=existing.get("serialNumber", "")),
        TextField(
            "purchase_price", "Purchase Price", default=str(existing.get("purchasePrice", ""))
        ),
    ]
    existing_imgs = item_images(existing)
    if existing_imgs:
        fields.append(ImageManagerField("existing_images", "Images", images=existing_imgs))
    fields.append(MultiImagePathField("new_image_paths", "New Images (comma-separated paths)"))
    return FormSpec(
        title="Edit Item" if existing else "New Item",
        fields=fields,
        submit_label="Save",
    )


def profile_form_spec(user: dict) -> FormSpec:
    """bi_python's _ProfileFormScreen. Result dict on submit:
    {name, email, about, show_on_users_page, password, image_path}
    consumed by core.api.update_user.

    NOTE (fixed vs bi_python): unlike create/edit Bin/Item, bi_python's
    original profile form had no image-manager row and no image-not-found
    retry loop on submit — both confirmed inconsistencies. The retry loop is
    fixed uniformly via core.policy.submit_with_image_retry regardless of
    which form calls it, so nothing form-shape-specific needs fixing here;
    still omitting an ImageManagerField deliberately, since bi_python's
    profile form only ever supported replacing the single profile image
    wholesale (image_path), never viewing/deleting it via a manager screen —
    that's a real UX gap worth a future enhancement, not part of this
    foundation increment's scope."""
    return FormSpec(
        title="Edit Profile",
        fields=[
            TextField(
                "name",
                "Name",
                required=True,
                validator=_non_blank("Name"),
                default=user.get("name", ""),
            ),
            TextField(
                "email",
                "Email",
                required=True,
                validator=_non_blank("Email"),
                default=user.get("email", ""),
            ),
            TextField("about", "About", default=user.get("about", "")),
            SwitchField(
                "show_on_users_page",
                "Show on Users Page",
                default=bool(user.get("showOnUsersPage")),
            ),
            PasswordField("password", "New Password (leave blank to keep current)"),
            ImagePathField("image_path", "New Image Path"),
        ],
        submit_label="Save",
    )


def search_form_spec() -> FormSpec:
    """bi_python's _SearchFormScreen. Single field; the renderer's text-prompt
    (not a full multi-field form in bi_python, but modeled as a one-field
    FormSpec here for consistency — a renderer is free to present a
    single-field FormSpec as a bare prompt if that's simpler for its idiom).
    A blank Enter submit is a deliberate distinct answer from Esc-cancel — see
    specs.fields.TextField/TextPromptSpec's distinguish_empty_submit for the
    general mechanism; here it's expressed by the field simply having no
    `required=True`/validator, so an empty result dict value is valid and the
    caller (core.flow's "search" node) decides what an empty query means."""
    return FormSpec(
        title="Search Items",
        fields=[TextField("query", "Search")],
        submit_label="Search",
    )


def login_form_spec() -> FormSpec:
    """bi_python's _LoginFormScreen. Result dict: {email, password}."""
    return FormSpec(
        title="Login",
        fields=[
            TextField("email", "Email", required=True, validator=_non_blank("Email")),
            PasswordField("password", "Password", required=True, validator=_non_blank("Password")),
        ],
        submit_label="Login",
    )


def signup_form_spec() -> FormSpec:
    """bi_python's _SignupFormScreen. Result dict:
    {name, email, password, show_on_users_page, image_path}.
    Password has no client-side length validation, matching bi_python (only
    non-blank is checked) — the backend's actual minimum isn't enforced
    client-side there either, so this isn't a regression."""
    return FormSpec(
        title="Sign Up",
        fields=[
            TextField("name", "Name", required=True, validator=_non_blank("Name")),
            TextField("email", "Email", required=True, validator=_non_blank("Email")),
            PasswordField(
                "password",
                "Password",
                required=True,
                validator=_non_blank("Password"),
                placeholder="min 8 chars",
            ),
            SwitchField("show_on_users_page", "Show on Users Page"),
            ImagePathField("image_path", "Profile Image Path"),
        ],
        submit_label="Sign Up",
    )
