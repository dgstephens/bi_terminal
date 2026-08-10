"""Unit tests for core.api.BinInventoryAPI — bi_python had zero test coverage
here; this is new, not a port. All HTTP calls are mocked; no network access."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from bi_terminal.core.api import BinInventoryAPI
from bi_terminal.core.errors import APIError, ImageFileNotFoundError


def _resp(json_body=None, ok=True, status_code=200, text=""):
    r = MagicMock()
    r.ok = ok
    r.status_code = status_code
    r.json.return_value = json_body if json_body is not None else {}
    r.text = text
    return r


@patch("bi_terminal.core.api.requests.post")
def test_login_posts_credentials(mock_post):
    mock_post.return_value = _resp({"token": "t", "userId": "u1", "email": "a@b.com"})
    api = BinInventoryAPI("https://api.example.com/api")
    result = api.login("a@b.com", "hunter2")
    mock_post.assert_called_once_with(
        "https://api.example.com/api/users/login",
        json={"email": "a@b.com", "password": "hunter2"},
        timeout=15,
    )
    assert result["token"] == "t"


@patch("bi_terminal.core.api.requests.get")
def test_get_bins_by_user_sends_bearer_token(mock_get):
    mock_get.return_value = _resp({"bins": []})
    api = BinInventoryAPI("https://api.example.com/api", token="abc123")
    api.get_bins_by_user("u1")
    _, kwargs = mock_get.call_args
    assert kwargs["headers"] == {"Authorization": "Bearer abc123"}


@patch("bi_terminal.core.api.requests.get")
def test_no_token_sends_no_auth_header(mock_get):
    mock_get.return_value = _resp({"bins": []})
    api = BinInventoryAPI("https://api.example.com/api")
    api.get_bins_by_user("u1")
    _, kwargs = mock_get.call_args
    assert kwargs["headers"] == {}


@patch("bi_terminal.core.api.requests.get")
def test_check_raises_apierror_with_status_code_on_failure(mock_get):
    mock_get.return_value = _resp({"message": "not found"}, ok=False, status_code=404)
    api = BinInventoryAPI("https://api.example.com/api")
    with pytest.raises(APIError) as exc_info:
        api.get_bin("missing")
    assert exc_info.value.status_code == 404
    assert "not found" in str(exc_info.value)


# ── Connection-level failures (no internet) ──────────────────────────────
# Real, live-reported bug (2026-08-10): "bi-terminal-textual crashes without
# internet". Root cause: every endpoint method called requests.get/post/etc
# directly, with the only try/except wrapping _check() (HTTP error
# *responses*). A ConnectionError/Timeout when genuinely offline is a
# different exception type than APIError -- nothing caught it, so it
# crashed the whole app. Fixed once, centrally, in _request(). These tests
# cover every requests.exceptions.RequestException subclass that can
# realistically happen when offline, across both call shapes in this file
# (plain requests.get/post/delete, and _send_form's multipart/JSON path),
# to make sure the central fix actually reaches every call site.


@patch("bi_terminal.core.api.requests.get")
def test_connection_error_becomes_apierror_not_a_crash(mock_get):
    mock_get.side_effect = requests.exceptions.ConnectionError("no route to host")
    api = BinInventoryAPI("https://api.example.com/api")
    with pytest.raises(APIError) as exc_info:
        api.get_bins_by_user("u1")
    assert exc_info.value.status_code == 0  # no HTTP response was ever received
    assert "Could not reach" in str(exc_info.value)


@patch("bi_terminal.core.api.requests.post")
def test_timeout_becomes_apierror(mock_post):
    mock_post.side_effect = requests.exceptions.Timeout("timed out")
    api = BinInventoryAPI("https://api.example.com/api")
    with pytest.raises(APIError):
        api.login("a@b.com", "hunter2")


@patch("bi_terminal.core.api.requests.post")
def test_send_form_json_path_also_wraps_connection_errors(mock_post):
    """_send_form's no-files (JSON) branch is a separate call shape from
    the plain requests.get/post ones above -- covered separately since it's
    exactly the kind of second call shape a manual per-site fix could have
    missed."""
    mock_post.side_effect = requests.exceptions.ConnectionError("offline")
    api = BinInventoryAPI("https://api.example.com/api")
    with pytest.raises(APIError):
        api.signup("Daniel", "a@b.com", "hunter2")


@patch("bi_terminal.core.api.requests.post")
def test_send_form_multipart_path_also_wraps_connection_errors(mock_post, tmp_path):
    """_send_form's files branch -- the third and last distinct call
    shape in this module."""
    image = tmp_path / "photo.jpg"
    image.write_bytes(b"fake image bytes")
    mock_post.side_effect = requests.exceptions.ConnectionError("offline")
    api = BinInventoryAPI("https://api.example.com/api")
    with pytest.raises(APIError):
        api.signup("Daniel", "a@b.com", "hunter2", image_path=str(image))


@patch("bi_terminal.core.api.requests.get")
def test_get_shared_bins_normalizes_singular_bin_key(mock_get):
    """Confirmed real backend quirk: this endpoint alone returns {"bin": [...]}
    (singular), unlike every other list endpoint's plural key. core.api shims
    it so callers only ever see "bins"."""
    mock_get.return_value = _resp({"bin": [{"id": "1", "binName": "Shelf A"}]})
    api = BinInventoryAPI("https://api.example.com/api", token="t")
    result = api.get_shared_bins("u1")
    assert result["bins"] == [{"id": "1", "binName": "Shelf A"}]


def test_create_bin_with_missing_image_path_raises_typed_error(tmp_path):
    api = BinInventoryAPI("https://api.example.com/api", token="t")
    bad_path = str(tmp_path / "does-not-exist.png")
    with pytest.raises(ImageFileNotFoundError) as exc_info:
        api.create_bin("Bin", "desc", "loc", "type", False, "u1", image_path=bad_path)
    assert exc_info.value.path == bad_path
    assert isinstance(exc_info.value, APIError)


@patch("bi_terminal.core.api.requests.post")
def test_create_bin_sends_public_as_lowercase_string(mock_post):
    mock_post.return_value = _resp({"bin": {"id": "1"}})
    api = BinInventoryAPI("https://api.example.com/api", token="t")
    api.create_bin("Bin", "desc", "loc", "type", True, "u1")
    _, kwargs = mock_post.call_args
    assert kwargs["json"]["public"] == "true"


@patch("bi_terminal.core.api.requests.patch")
def test_update_item_repeats_existing_images_as_list(mock_patch):
    mock_patch.return_value = _resp({"thisItem": {"id": "i1"}})
    api = BinInventoryAPI("https://api.example.com/api", token="t")
    api.update_item(
        "i1",
        "Widget",
        "bin1",
        "u1",
        existing_images=["https://x/1.png", "https://x/2.png"],
    )
    _, kwargs = mock_patch.call_args
    assert kwargs["json"]["existingImages"] == ["https://x/1.png", "https://x/2.png"]


@patch("bi_terminal.core.api.requests.post")
def test_search_items_posts_query_only(mock_post):
    mock_post.return_value = _resp({"items": []})
    api = BinInventoryAPI("https://api.example.com/api", token="t")
    api.search_items("widget")
    mock_post.assert_called_once_with(
        "https://api.example.com/api/items/search",
        json={"q": "widget"},
        headers={"Authorization": "Bearer t"},
        timeout=15,
    )
