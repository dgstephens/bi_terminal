"""AppDriver — the renderer-agnostic flow orchestration shared by every
renderer's app.

Extracted from renderers/textual/app.py (originally BiTerminalTextualApp's
methods) once it became clear, while scoping the ANSI door renderer, that
none of this ~700-line flow graph actually touches Textual APIs except at
two seams: exiting the app, and unwinding a global-nav jump. Every other
line only calls self.renderer.show_*/notify, self.client.* (core.api), or
self.cfg — already 100% renderer-agnostic. Duplicating it into a second
renderer would contradict this whole project's premise (one core+spec, N
renderers) and create N places every future business-logic fix has to land.

Lives at the top level (sibling to core/, specs/, renderers/) — NOT inside
core/, to keep core/'s "never import renderers" invariant
(tests/test_layering.py) unambiguous. This module imports
renderers.base.Renderer only as a type hint (a zero-toolkit-dependency
Protocol module), so it doesn't pull in Textual or any concrete rendering
toolkit either — it depends on the Renderer *contract*, not any
implementation of it.

Direct sync port of bi_python's app.py flow graph — same control flow, same
order of operations, same notify messages. No asyncio.to_thread anywhere:
core.api calls are just plain blocking calls; only renderer.show_*/notify
need to cross back into whatever event loop (if any) the renderer's host
needs — that's each renderer's own problem (Textual bridges it via
call_from_thread; a stdio door doesn't have one to begin with).
"""

import os
from typing import TYPE_CHECKING, Optional

from .core import config
from .core.api import BinInventoryAPI
from .core.errors import APIError
from .core.flow import GlobalNavigate
from .core.models import (
    DEFAULT_BIN_IMAGE_URL,
    fmt_date,
    item_images,
    prev_bin_id_from_item,
    prev_bin_name_from_item,
    repopulate_item_bin_refs,
)
from .core.policy import fetch_list, submit_with_image_retry
from .specs.base import CANCELLED, EMPTY_SUBMIT
from .specs.fields import ConfirmSpec, TextPromptSpec
from .specs.forms import (
    bin_form_spec,
    item_form_spec,
    login_form_spec,
    profile_form_spec,
    retry_image_path_spec,
    retry_image_paths_spec,
    signup_form_spec,
)
from .specs.menus import (
    all_items_spec,
    bin_detail_menu_spec,
    item_detail_menu_spec,
    items_in_bin_spec,
    login_choice_spec,
    main_menu_spec,
    my_bins_spec,
    profile_menu_spec,
    search_results_spec,
    settings_menu_spec,
    shared_bin_items_spec,
    shared_bins_spec,
)

if TYPE_CHECKING:
    from .renderers.base import Renderer


class _Bubble(Exception):
    """Internal-only: wraps a GlobalNavigate so it can unwind run()'s nested
    sync call graph, exactly like bi_python's NavigateTo(Exception) did for
    its nested awaits. Never crosses the Renderer protocol boundary — every
    renderer's show_action_menu still returns a plain GlobalNavigate value
    per the documented contract (renderers/base.py); only this driver
    converts it into a raised exception."""

    def __init__(self, nav: GlobalNavigate):
        self.nav = nav
        super().__init__(nav.dest)


class AppDriver:
    """Owns cfg/client/renderer and the entire flow graph. `renderer` is
    anything implementing the Renderer protocol — duck-typed, no import of
    any concrete renderer needed here.

    `on_global_navigate`: called (with no args) whenever a global-nav digit
    jump needs to unwind renderer-specific presentation state — e.g.
    Textual's pushed-screen stack. Defaults to a no-op (correct for a
    renderer with no persistent stack to unwind, e.g. a linear print-based
    door — the exception unwind through Python's own call stack is the
    entire mechanism there).

    `on_exit`: called (with no args) when the flow naturally concludes
    (Exit chosen, or Esc from the outermost screen). Defaults to a no-op;
    Textual uses it to actually call App.exit() via call_from_thread; a
    stdio door might use it to print a goodbye line.
    """

    def __init__(
        self,
        cfg: dict,
        client: BinInventoryAPI,
        renderer: "Renderer",
        on_global_navigate=None,
        on_exit=None,
    ) -> None:
        self.cfg = cfg
        self.client = client
        self.renderer = renderer
        self._on_global_navigate = on_global_navigate or (lambda: None)
        self._on_exit = on_exit or (lambda: None)

    # ── Driver ───────────────────────────────────────────────────────────

    def run(self) -> None:
        if not self.cfg.get("token"):
            if not self._login_flow():
                return  # on_exit already called; stop looping.

        dest = "main"
        while True:
            try:
                if dest == "bins":
                    self._bins_menu()
                    dest = "main"
                elif dest == "items":
                    self._all_items_menu()
                    dest = "main"
                elif dest == "search":
                    self._search_menu()
                    dest = "main"
                elif dest == "shared":
                    self._shared_bins_menu()
                    dest = "main"
                elif dest == "logout":
                    if not self._login_flow():
                        return
                    dest = "main"
                else:
                    dest = self._main_dispatch()
                if dest is None:
                    return  # on_exit already called; stop looping.
            except _Bubble as bubble:
                self._on_global_navigate()
                dest = bubble.nav.dest if bubble.nav.dest in ("main", "bins", "items", "search") else "main"

    def _menu(self, spec):
        """Push an ActionMenuSpec and convert a GlobalNavigate result into a
        real raised exception, so it propagates up through this method's
        nested sync callers — exactly like bi_python's show_action_menu()
        wrapper did for its nested awaits."""
        result = self.renderer.show_action_menu(spec)
        if isinstance(result, GlobalNavigate):
            raise _Bubble(result)
        return result

    # ── Login / Signup ──────────────────────────────────────────────────

    def _login_flow(self) -> bool:
        """Show Login/Signup/Exit until self.cfg has a valid token, or the
        user exits. No global-nav digits here (login_choice_spec's
        nav_enabled=False) — nothing for 1/2/3/4 to jump to before the user
        is authenticated. Returns True once logged in; False if the user
        chose Exit (on_exit already called by then)."""
        while True:
            action = self.renderer.show_action_menu(login_choice_spec())
            if action is CANCELLED or action == "exit":
                self._on_exit()
                return False
            elif action == "login":
                if self._do_login():
                    return True
            elif action == "signup":
                if self._do_signup():
                    return True

    def _do_login(self) -> bool:
        result = self.renderer.show_form(login_form_spec())
        if result is CANCELLED:
            return False
        try:
            data = self.client.login(result["email"], result["password"])
            self.cfg.update({"token": data["token"], "userId": data["userId"], "email": data["email"]})
            config.save(self.cfg)
            self.client.token = data["token"]
            self.renderer.notify(f"Logged in as {result['email']}")
            return True
        except APIError as e:
            self.renderer.notify(str(e), severity="error")
            return False

    def _do_signup(self) -> bool:
        result = self.renderer.show_form(signup_form_spec())
        if result is CANCELLED:
            return False
        image_path = result["image_path"]
        if image_path and not os.path.exists(image_path):
            self.renderer.notify(f"File not found, skipping: {image_path}", severity="warning")
            image_path = None
        try:
            data = self.client.signup(
                name=result["name"],
                email=result["email"],
                password=result["password"],
                show_on_users_page=result["show_on_users_page"],
                image_path=image_path,
            )
            self.cfg.update({"token": data["token"], "userId": data["userId"], "email": data["email"]})
            config.save(self.cfg)
            self.client.token = data["token"]
            self.renderer.notify(f"Account created! Logged in as {result['email']}")
            return True
        except APIError as e:
            self.renderer.notify(str(e), severity="error")
            return False

    # ── Main menu ────────────────────────────────────────────────────────

    def _main_dispatch(self) -> Optional[str]:
        try:
            count_data = self.client.get_item_count(self.cfg["userId"])
            item_count = count_data.get("number", "?")
        except APIError:
            item_count = "?"

        action = self._menu(main_menu_spec(item_count, self.cfg.get("email", "")))

        if action is CANCELLED or action == "exit":
            self._on_exit()
            return None
        elif action == "logout":
            config.clear_auth(self.cfg)
            self.client.token = None
            self.renderer.notify("Logged out.")
            return "logout"
        elif action in ("bins", "items", "search", "shared"):
            return action
        elif action == "new_bin":
            self._create_bin()
        elif action == "new_item":
            self._create_item()
        elif action == "profile":
            self._profile_menu()
        elif action == "settings":
            self._settings_menu()

        return "main"

    # ── Bins ─────────────────────────────────────────────────────────────

    def _bins_menu(self) -> None:
        while True:
            bins, error = fetch_list(self.client.get_bins_by_user, self.cfg["userId"], result_key="bins")
            if error is not None:
                self.renderer.notify(str(error), severity="error")
                return

            result = self.renderer.show_list_picker(my_bins_spec(bins))
            if result is CANCELLED:
                return
            action, payload = result

            if action == "back":
                return
            elif action == "new":
                self._create_bin()
            elif action == "open":
                self._bin_detail(payload)

    def _bin_detail(self, bin_data: dict) -> None:
        b = bin_data
        while True:
            action = self._menu(bin_detail_menu_spec(b))
            if action is CANCELLED or action == "back":
                return
            elif action == "items":
                self._items_in_bin_menu(b)
            elif action == "view_image":
                self.renderer.show_image([b["image"]])
            elif action == "edit":
                updated = self._edit_bin(b)
                if updated:
                    b = updated
            elif action == "delete":
                confirmed = self.renderer.show_confirm(
                    ConfirmSpec(prompt=f"Delete '{b['binName']}'? Items will be moved to 'no bin'.")
                )
                if confirmed:
                    try:
                        self.client.delete_bin(b["id"])
                        self.renderer.notify("Bin deleted.")
                        return
                    except APIError as e:
                        self.renderer.notify(str(e), severity="error")

    def _create_bin(self) -> None:
        result = self.renderer.show_form(bin_form_spec())
        if result is CANCELLED:
            return

        state = {"image_path": result["image_path"]}

        def submit():
            return self.client.create_bin(
                bin_name=result["bin_name"],
                description=result["description"],
                location=result["location"],
                bin_type=result["bin_type"],
                public=result["public"],
                user_id=self.cfg["userId"],
                sw_emails=result["sw_emails"],
                image_path=state["image_path"],
            )

        _response, error = submit_with_image_retry(
            submit, self._ask_retry_image_path, lambda p: state.__setitem__("image_path", p)
        )
        if error is not None:
            self.renderer.notify(str(error), severity="error")
            return
        self.renderer.notify(f"Bin '{result['bin_name']}' created.")

    def _edit_bin(self, b: dict) -> Optional[dict]:
        result = self.renderer.show_form(bin_form_spec(existing=b))
        if result is CANCELLED:
            return None

        # FormScreen's ImageManagerField always dismisses the full image
        # list under the field's own name (a deliberately generic contract
        # — see specs.fields.ImageManagerField); the bin-specific "reduce to
        # a single current-image string, falling back to
        # DEFAULT_BIN_IMAGE_URL if emptied" business rule lives HERE, in the
        # bin-specific driver code, not inside the generic form widget.
        if "current_image" in result:
            imgs = result["current_image"] or []
            current_image = imgs[0] if imgs else DEFAULT_BIN_IMAGE_URL
        else:
            current_image = b.get("image", "")

        state = {"image_path": result["image_path"]}

        def submit():
            return self.client.update_bin(
                bin_id=b["id"],
                bin_name=result["bin_name"],
                description=result["description"],
                location=result["location"],
                bin_type=result["bin_type"],
                public=result["public"],
                user_id=self.cfg["userId"],
                sw_emails=result["sw_emails"],
                image_path=state["image_path"],
                current_image=current_image,
            )

        response, error = submit_with_image_retry(
            submit, self._ask_retry_image_path, lambda p: state.__setitem__("image_path", p)
        )
        if error is not None:
            self.renderer.notify(str(error), severity="error")
            return None
        self.renderer.notify("Bin updated.")
        return response.get("bin", b)

    def _ask_retry_image_path(self, _bad_path: str) -> Optional[str]:
        """Re-prompt for a single image path after an 'Image file not
        found' error. A falsy return (CANCELLED or blank submit) tells
        core.policy.submit_with_image_retry to give up the retry loop."""
        prompt_result = self.renderer.show_text_prompt(retry_image_path_spec())
        return None if prompt_result in (CANCELLED, "") else prompt_result

    def _ask_retry_image_paths_raw(self, _bad_path: str) -> Optional[str]:
        """Same as _ask_retry_image_path but for the comma-separated
        multi-path prompt used by the Item form's retry loop — returns the
        raw string (the paired set_paths closure splits it), not a list."""
        prompt_result = self.renderer.show_text_prompt(retry_image_paths_spec())
        return None if prompt_result in (CANCELLED, "") else prompt_result

    # ── Items ────────────────────────────────────────────────────────────

    def _all_items_menu(self) -> None:
        while True:
            items, error = fetch_list(self.client.get_items_by_user, self.cfg["userId"], result_key="items")
            if error is not None:
                self.renderer.notify(str(error), severity="error")
                return

            result = self.renderer.show_list_picker(all_items_spec(items))
            if result is CANCELLED:
                return
            action, payload = result

            if action == "back":
                return
            elif action == "new":
                self._create_item()
            elif action == "open":
                bins, _err = fetch_list(self.client.get_bins_by_user, self.cfg["userId"], result_key="bins")
                self._item_detail(payload, bins)

    def _items_in_bin_menu(self, bin_data: dict) -> None:
        while True:
            items, error = fetch_list(self.client.get_items_by_bin, bin_data["id"], result_key="items")
            if error is not None:
                self.renderer.notify(str(error), severity="error")
                return

            result = self.renderer.show_list_picker(items_in_bin_spec(items, bin_data))
            if result is CANCELLED:
                return
            action, payload = result

            if action == "back":
                return
            elif action == "new":
                self._create_item(preselect_bin=bin_data)
            elif action == "open":
                bins, _err = fetch_list(self.client.get_bins_by_user, self.cfg["userId"], result_key="bins")
                self._item_detail(payload, bins)

    def _item_detail(self, item_data: dict, bins: list) -> None:
        it = item_data
        while True:
            action = self._menu(item_detail_menu_spec(it))
            if action is CANCELLED or action == "back":
                return
            elif action == "view_image":
                self.renderer.show_image(item_images(it))
            elif action == "edit":
                updated = self._edit_item(it, bins)
                if updated:
                    it = updated
            elif action == "delete":
                confirmed = self.renderer.show_confirm(
                    ConfirmSpec(prompt=f"Permanently delete '{it['item']}'?")
                )
                if confirmed:
                    try:
                        self.client.delete_item(it["id"])
                        self.renderer.notify("Item deleted.")
                        return
                    except APIError as e:
                        self.renderer.notify(str(e), severity="error")
            elif action == "move_prev":
                prev_bin_id = prev_bin_id_from_item(it)
                prev_name = prev_bin_name_from_item(it)
                if prev_bin_id:
                    try:
                        result = self.client.update_item(
                            item_id=it["id"],
                            item=it.get("item", ""),
                            bin_id=prev_bin_id,
                            user_id=self.cfg["userId"],
                            description=it.get("description", "") or "",
                            story=it.get("story", "") or "",
                            item_type=it.get("type", "") or "",
                            quantity=str(it.get("quantity", "")) if it.get("quantity") is not None else "",
                            purchase_date=fmt_date(it.get("purchaseDate")) or "",
                            purchased_from=it.get("purchasedFrom", "") or "",
                            manufacturer=it.get("manufacturer", "") or "",
                            date_of_manufacture=fmt_date(it.get("dateOfManufacture")) or "",
                            serial_number=it.get("serialNumber", "") or "",
                            purchase_price=(
                                str(it.get("purchasePrice", ""))
                                if it.get("purchasePrice") is not None
                                else ""
                            ),
                            existing_images=item_images(it),
                        )
                        self.renderer.notify(f"Moved back to '{prev_name}'.")
                        it = repopulate_item_bin_refs(result.get("thisItem", it), bins)
                    except APIError as e:
                        self.renderer.notify(str(e), severity="error")

    def _create_item(self, preselect_bin: Optional[dict] = None) -> None:
        bins, error = fetch_list(self.client.get_bins_by_user, self.cfg["userId"], result_key="bins")
        if error is not None:
            self.renderer.notify(str(error), severity="error")
            return
        if not bins:
            self.renderer.notify("No bins found. Create a bin first.", severity="error")
            return

        preselect_id = preselect_bin["id"] if preselect_bin else None
        result = self.renderer.show_form(item_form_spec(bins, preselect_bin_id=preselect_id))
        if result is CANCELLED:
            return

        state = {"image_paths": result["new_image_paths"]}

        def submit():
            return self.client.create_item(
                item=result["item"],
                bin_id=result["bin_id"],
                user_id=self.cfg["userId"],
                description=result["description"],
                story=result["story"],
                item_type=result["item_type"],
                quantity=result["quantity"],
                purchase_date=result["purchase_date"],
                purchased_from=result["purchased_from"],
                manufacturer=result["manufacturer"],
                date_of_manufacture=result["date_of_manufacture"],
                serial_number=result["serial_number"],
                purchase_price=result["purchase_price"],
                image_paths=state["image_paths"],
            )

        _response, error = submit_with_image_retry(
            submit, self._ask_retry_image_paths_raw, lambda raw: self._set_paths(state, raw)
        )
        if error is not None:
            self.renderer.notify(str(error), severity="error")
            return
        self.renderer.notify(f"Item '{result['item']}' created.")

    def _edit_item(self, it: dict, bins: list) -> Optional[dict]:
        result = self.renderer.show_form(item_form_spec(bins, existing=it))
        if result is CANCELLED:
            return None

        state = {"image_paths": result["new_image_paths"]}

        def submit():
            return self.client.update_item(
                item_id=it["id"],
                item=result["item"],
                bin_id=result["bin_id"],
                user_id=self.cfg["userId"],
                description=result["description"],
                story=result["story"],
                item_type=result["item_type"],
                quantity=result["quantity"],
                purchase_date=result["purchase_date"],
                purchased_from=result["purchased_from"],
                manufacturer=result["manufacturer"],
                date_of_manufacture=result["date_of_manufacture"],
                serial_number=result["serial_number"],
                purchase_price=result["purchase_price"],
                # "existing_images" is only a key in `result` when the item
                # actually had existing images to manage — item_form_spec
                # only adds the ImageManagerField in that case (see
                # specs/forms.py), so a renderer's form-runner never
                # populates the key otherwise. Defaults to [] (nothing to
                # keep), matching bi_python's _ItemFormScreen, which always
                # initialized self._remaining_images to [] regardless of
                # whether the manager row was shown.
                existing_images=result.get("existing_images", []),
                new_image_paths=state["image_paths"],
            )

        response, error = submit_with_image_retry(
            submit, self._ask_retry_image_paths_raw, lambda raw: self._set_paths(state, raw)
        )
        if error is not None:
            self.renderer.notify(str(error), severity="error")
            return None
        self.renderer.notify("Item updated.")
        return repopulate_item_bin_refs(response.get("thisItem", it), bins)

    @staticmethod
    def _set_paths(state: dict, raw: str) -> None:
        state["image_paths"] = [p.strip() for p in raw.split(",") if p.strip()]

    # ── Search ───────────────────────────────────────────────────────────

    def _search_menu(self) -> None:
        while True:
            # A TextPromptSpec, not a one-field FormSpec -- search must submit
            # on a bare Enter (matching every other renderer's text-prompt
            # contract), not require Ctrl+S like a multi-field form. This was
            # a real regression (reported live, 2026-08-09): search had been
            # built as `show_form(search_form_spec())` instead, which forced
            # Ctrl+S in the Textual renderer and had no working Enter-submits
            # at all in the door renderers either -- the same bug, once, in
            # the one shared driver, not four separate renderer-specific
            # bugs. distinguish_empty_submit=True is exactly what
            # TextPromptSpec's own docstring says it exists for: telling a
            # deliberate blank Enter (EMPTY_SUBMIT, "try again" notice) apart
            # from Esc (CANCELLED, silently back to main menu).
            result = self.renderer.show_text_prompt(
                TextPromptSpec(title="Search Items", prompt="Search", distinguish_empty_submit=True)
            )
            if result is CANCELLED:
                return  # Esc = cancel, back to main menu
            query = "" if result is EMPTY_SUBMIT else result
            if not query:
                self.renderer.notify(
                    "You didn't search for anything. Please type something and try again.",
                    severity="warning",
                )
                continue

            try:
                data = self.client.search_items(query)
                items = data.get("items", [])
            except APIError:
                items = []

            if not items:
                self.renderer.notify("No results found.", severity="warning")
                continue

            if len(items) == 1:
                # Single match: open it directly instead of showing a picker
                # with only one real choice — see search_results_spec's
                # docstring for the reflexive-double-Enter race this avoids.
                bins, _err = fetch_list(self.client.get_bins_by_user, self.cfg["userId"], result_key="bins")
                self._item_detail(items[0], bins)
                continue

            result2 = self.renderer.show_list_picker(search_results_spec(items, query))
            if result2 is CANCELLED:
                continue
            action, payload = result2

            if action == "back":
                continue
            elif action == "open":
                bins, _err = fetch_list(self.client.get_bins_by_user, self.cfg["userId"], result_key="bins")
                self._item_detail(payload, bins)

    # ── Shared Bins ──────────────────────────────────────────────────────

    def _shared_bins_menu(self) -> None:
        bins, error = fetch_list(self.client.get_shared_bins, self.cfg["userId"], result_key="bins")
        # Unlike bi_python (which swallowed ALL errors here to an empty
        # list), a non-404 error now surfaces via `error` below — the
        # confirmed, deliberate behavior fix from the foundation increment
        # (core/policy.py's module docstring) taking effect for real here.
        if error is not None:
            self.renderer.notify(str(error), severity="error")
            return
        if not bins:
            self.renderer.notify("No bins have been shared with you.", severity="warning")
            return

        while True:
            result = self.renderer.show_list_picker(shared_bins_spec(bins))
            if result is CANCELLED:
                return
            action, payload = result

            if action == "back":
                return
            elif action == "open":
                self._shared_bin_items_view(payload)

    def _shared_bin_items_view(self, bin_data: dict) -> None:
        items, error = fetch_list(self.client.get_items_by_bin, bin_data["id"], result_key="items")
        if error is not None:
            self.renderer.notify(str(error), severity="error")
            return
        if not items:
            self.renderer.notify(f"No items in '{bin_data.get('binName', '')}'.", severity="warning")
            return

        while True:
            result = self.renderer.show_list_picker(shared_bin_items_spec(items, bin_data))
            if result is CANCELLED:
                return
            action, payload = result

            if action == "back":
                return
            elif action == "open":
                # Fetch the user's own bins first — bi_python's confirmed
                # bug (passed bins=[] here, breaking bin-ref repopulation
                # for a shared item's edit/move-to-prev-bin) is fixed by
                # this fetch, per the foundation-increment plan.
                bins, _err = fetch_list(self.client.get_bins_by_user, self.cfg["userId"], result_key="bins")
                self._item_detail(payload, bins)

    # ── Profile ──────────────────────────────────────────────────────────

    def _profile_menu(self) -> None:
        while True:
            try:
                data = self.client.get_user(self.cfg["userId"])
                user = data.get("user", {})
            except APIError as e:
                self.renderer.notify(str(e), severity="error")
                return

            action = self._menu(profile_menu_spec(user))
            if action is CANCELLED or action == "back":
                return
            elif action == "view_image":
                self.renderer.show_image([user["image"]])
            elif action == "edit":
                self._edit_profile(user)

    def _edit_profile(self, user: dict) -> None:
        result = self.renderer.show_form(profile_form_spec(user))
        if result is CANCELLED:
            return

        state = {"image_path": result["image_path"]}

        def submit():
            return self.client.update_user(
                user_id=self.cfg["userId"],
                name=result["name"],
                email=result["email"],
                about=result["about"],
                password=result["password"],
                show_on_users_page=result["show_on_users_page"],
                image_path=state["image_path"],
                current_image=user.get("image", ""),
            )

        # bi_python's edit_profile had NO image-retry loop, unlike Bin/Item
        # forms — a confirmed inconsistency, fixed here since the mechanism
        # (core.policy.submit_with_image_retry) is now shared uniformly.
        _response, error = submit_with_image_retry(
            submit, self._ask_retry_image_path, lambda p: state.__setitem__("image_path", p)
        )
        if error is not None:
            self.renderer.notify(str(error), severity="error")
            return

        if result["email"] != self.cfg.get("email"):
            self.cfg["email"] = result["email"]
            config.save(self.cfg)
        self.renderer.notify("Profile updated.")

    # ── Settings ─────────────────────────────────────────────────────────

    def _settings_menu(self) -> None:
        current = self.cfg.get("image_mode", "none")
        mode = self._menu(settings_menu_spec(current))
        if mode is CANCELLED or mode == "back":
            return

        self.cfg["image_mode"] = mode
        config.save(self.cfg)
        # Renderer-agnostic on purpose: this driver never reaches into a
        # renderer's internal image_mode/image_capability state. Each
        # renderer is responsible for reflecting cfg["image_mode"] live on
        # its own (TextualRenderer does this via a property that reads
        # self.app.cfg fresh on every access, matching bi_python's own
        # fresh-read design) — an earlier version of this method mutated
        # TextualRenderer's cached attributes directly, which would have
        # broken the moment a second renderer needed the same update.
        labels = {"none": "No images", "ansi": "ANSI color blocks", "ascii": "ASCII art"}
        self.renderer.notify(f"Image mode set to: {labels[mode]}")
