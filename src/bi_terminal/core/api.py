"""Binventory backend API client.

Ported near-verbatim from bi_python/api.py (already renderer-agnostic there —
plain `requests`, no asyncio/UI concerns). Two deliberate deviations from the
original, both fixes carried over from the bi_terminal planning session:

1. `_open_file`/`_open_files` raise the typed `ImageFileNotFoundError` (see
   errors.py) instead of a plain `APIError` whose message callers used to
   string-match.
2. `get_shared_bins` normalizes its response to `{"bins": [...]}` — the
   backend genuinely returns `{"bin": [...]}` (singular) from this one
   endpoint, inconsistent with every other list endpoint's plural key. Shimmed
   client-side here, same pattern already used below for the binId/prevBin/
   thisItem response-shape quirks (see core/models.py).
"""

import os
from typing import List, Optional

import requests

from .errors import APIError, ImageFileNotFoundError


def _open_file(field: str, path: str) -> tuple:
    if not os.path.exists(path):
        raise ImageFileNotFoundError(path)
    return (field, open(path, "rb"))


def _open_files(field: str, paths: List[str]) -> list:
    return [_open_file(field, p) for p in paths]


class BinInventoryAPI:
    def __init__(self, base_url: str, token: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.token = token

    def _auth(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def _check(self, resp: requests.Response) -> dict:
        if not resp.ok:
            try:
                msg = resp.json().get("message", resp.text)
            except Exception:
                msg = resp.text
            raise APIError(msg, resp.status_code)
        try:
            return resp.json()
        except Exception:
            return {}

    def _send_form(self, method: str, url: str, data: list, files: list) -> dict:
        """Send as multipart when files are present, JSON otherwise.

        The backend uses multer for all mutating routes, which only parses
        multipart bodies. When there are no files, we fall back to JSON which
        bodyParser.json() (applied globally) handles correctly.
        """
        headers = self._auth()
        if files:
            resp = getattr(requests, method)(url, data=data, files=files, headers=headers)
        else:
            # Convert list-of-tuples to dict, collecting duplicate keys as lists
            body: dict = {}
            for k, v in data:
                if k in body:
                    if not isinstance(body[k], list):
                        body[k] = [body[k]]
                    body[k].append(v)
                else:
                    body[k] = v
            resp = getattr(requests, method)(url, json=body, headers=headers)
        return self._check(resp)

    # ── Auth ──────────────────────────────────────────────────────────────

    def login(self, email: str, password: str) -> dict:
        resp = requests.post(
            f"{self.base_url}/users/login",
            json={"email": email, "password": password},
        )
        return self._check(resp)

    def signup(
        self,
        name: str,
        email: str,
        password: str,
        show_on_users_page: bool = False,
        image_path: Optional[str] = None,
    ) -> dict:
        data = [
            ("name", name),
            ("email", email),
            ("password", password),
            ("showOnUsersPage", str(show_on_users_page).lower()),
        ]
        files = [_open_file("image", image_path)] if image_path else []
        return self._send_form("post", f"{self.base_url}/users/signup", data, files)

    # ── Users ─────────────────────────────────────────────────────────────

    def get_user(self, user_id: str) -> dict:
        resp = requests.get(f"{self.base_url}/users/{user_id}", headers=self._auth())
        return self._check(resp)

    def update_user(
        self,
        user_id: str,
        name: str,
        email: str,
        about: str = "",
        password: str = "",
        show_on_users_page: bool = False,
        image_path: Optional[str] = None,
        current_image: str = "",
    ) -> dict:
        data = [
            ("name", name),
            ("email", email),
            ("about", about),
            ("showOnUsersPage", str(show_on_users_page).lower()),
            ("image", current_image),
        ]
        if password:
            data.append(("password", password))
        files = [_open_file("image", image_path)] if image_path else []
        return self._send_form("patch", f"{self.base_url}/users/{user_id}", data, files)

    # ── Bins ──────────────────────────────────────────────────────────────

    def get_bin(self, bin_id: str) -> dict:
        resp = requests.get(f"{self.base_url}/bins/{bin_id}", headers=self._auth())
        return self._check(resp)

    def get_bins_by_user(self, user_id: str) -> dict:
        resp = requests.get(f"{self.base_url}/bins/user/{user_id}", headers=self._auth())
        return self._check(resp)

    def get_shared_bins(self, user_id: str) -> dict:
        """Returns {"bins": [...]} — normalized from the backend's actual
        {"bin": [...]} (singular) key, which is inconsistent with every other
        list endpoint here. See module docstring."""
        resp = requests.get(f"{self.base_url}/bins/user/shared/{user_id}", headers=self._auth())
        data = self._check(resp)
        if "bin" in data and "bins" not in data:
            data = {**data, "bins": data["bin"]}
        return data

    def create_bin(
        self,
        bin_name: str,
        description: str,
        location: str,
        bin_type: str,
        public: bool,
        user_id: str,
        sw_emails: str = "",
        image_path: Optional[str] = None,
    ) -> dict:
        data = [
            ("binName", bin_name),
            ("description", description),
            ("location", location),
            ("type", bin_type),
            ("public", str(public).lower()),
            ("userId", user_id),
            ("swEmails", sw_emails),
        ]
        files = [_open_file("image", image_path)] if image_path else []
        return self._send_form("post", f"{self.base_url}/bins/", data, files)

    def update_bin(
        self,
        bin_id: str,
        bin_name: str,
        description: str,
        location: str,
        bin_type: str,
        public: bool,
        user_id: str,
        sw_emails: str = "",
        image_path: Optional[str] = None,
        current_image: str = "",
    ) -> dict:
        data = [
            ("binName", bin_name),
            ("description", description),
            ("location", location),
            ("type", bin_type),
            ("public", str(public).lower()),
            ("userId", user_id),
            ("swEmails", sw_emails),
            ("image", current_image),
        ]
        files = [_open_file("image", image_path)] if image_path else []
        return self._send_form("patch", f"{self.base_url}/bins/{bin_id}", data, files)

    def delete_bin(self, bin_id: str) -> dict:
        resp = requests.delete(f"{self.base_url}/bins/{bin_id}", headers=self._auth())
        return self._check(resp)

    # ── Items ─────────────────────────────────────────────────────────────

    def get_item(self, item_id: str) -> dict:
        resp = requests.get(f"{self.base_url}/items/{item_id}", headers=self._auth())
        return self._check(resp)

    def get_items_by_user(self, user_id: str) -> dict:
        resp = requests.get(f"{self.base_url}/items/user/{user_id}", headers=self._auth())
        return self._check(resp)

    def get_items_by_bin(self, bin_id: str) -> dict:
        resp = requests.get(f"{self.base_url}/items/bin/{bin_id}", headers=self._auth())
        return self._check(resp)

    def search_items(self, query: str) -> dict:
        """POST /items/search, body {"q": query}. The backend handles
        multi-term "and" search natively server-side (splits on "and",
        searches item/description/manufacturer/purchasedFrom/type/
        serialNumber, ANDs the conditions). Results are scoped to the
        authenticated user via the JWT, not a request parameter — confirmed
        via bi_backend's IDOR audit, which moved searchItems off a
        client-supplied id onto req.userData.userId. (bi_python's version of
        this method kept a vestigial unused `user_id` parameter for call-site
        compatibility with an older client-side search implementation; dropped
        here since nothing in this codebase needs it.)
        """
        resp = requests.post(
            f"{self.base_url}/items/search",
            json={"q": query},
            headers=self._auth(),
        )
        return self._check(resp)

    def get_item_count(self, user_id: str) -> dict:
        resp = requests.get(
            f"{self.base_url}/items/items/number/{user_id}",
            headers=self._auth(),
        )
        return self._check(resp)

    def create_item(
        self,
        item: str,
        bin_id: str,
        user_id: str,
        description: str = "",
        story: str = "",
        item_type: str = "",
        quantity: str = "",
        purchase_date: str = "",
        purchased_from: str = "",
        manufacturer: str = "",
        date_of_manufacture: str = "",
        serial_number: str = "",
        purchase_price: str = "",
        image_paths: Optional[List[str]] = None,
    ) -> dict:
        data = [
            ("item", item),
            ("description", description),
            ("story", story),
            ("type", item_type),
            ("quantity", quantity),
            ("purchaseDate", purchase_date),
            ("purchasedFrom", purchased_from),
            ("manufacturer", manufacturer),
            ("dateOfManufacture", date_of_manufacture),
            ("serialNumber", serial_number),
            ("purchasePrice", purchase_price),
            ("binId", bin_id),
            ("userId", user_id),
        ]
        files = _open_files("images", image_paths or [])
        return self._send_form("post", f"{self.base_url}/items/", data, files)

    def update_item(
        self,
        item_id: str,
        item: str,
        bin_id: str,
        user_id: str,
        description: str = "",
        story: str = "",
        item_type: str = "",
        quantity: str = "",
        purchase_date: str = "",
        purchased_from: str = "",
        manufacturer: str = "",
        date_of_manufacture: str = "",
        serial_number: str = "",
        purchase_price: str = "",
        existing_images: Optional[List[str]] = None,
        new_image_paths: Optional[List[str]] = None,
    ) -> dict:
        data = [
            ("item", item),
            ("description", description),
            ("story", story),
            ("type", item_type),
            ("quantity", quantity),
            ("purchaseDate", purchase_date),
            ("purchasedFrom", purchased_from),
            ("manufacturer", manufacturer),
            ("dateOfManufacture", date_of_manufacture),
            ("serialNumber", serial_number),
            ("purchasePrice", purchase_price),
            ("binId", bin_id),
            ("userId", user_id),
        ]
        for url in (existing_images or []):
            data.append(("existingImages", url))
        files = _open_files("images", new_image_paths or [])
        return self._send_form("patch", f"{self.base_url}/items/{item_id}", data, files)

    def delete_item(self, item_id: str) -> dict:
        resp = requests.delete(f"{self.base_url}/items/{item_id}", headers=self._auth())
        return self._check(resp)
