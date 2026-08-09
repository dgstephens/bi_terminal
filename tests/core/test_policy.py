from bi_terminal.core.errors import APIError, ImageFileNotFoundError
from bi_terminal.core.policy import ListFetchPolicy, fetch_list, submit_with_image_retry


def test_fetch_list_success_returns_items_and_no_error():
    def fn():
        return {"bins": [{"id": "1"}]}

    items, error = fetch_list(fn, result_key="bins")
    assert items == [{"id": "1"}]
    assert error is None


def test_fetch_list_missing_key_returns_empty_list():
    def fn():
        return {}

    items, error = fetch_list(fn, result_key="bins")
    assert items == []
    assert error is None


def test_fetch_list_404_treated_as_empty_not_error():
    def fn():
        raise APIError("not found", status_code=404)

    items, error = fetch_list(fn, result_key="items", policy=ListFetchPolicy.EMPTY_ON_404)
    assert items == []
    assert error is None


def test_fetch_list_non_404_error_surfaces():
    def fn():
        raise APIError("server error", status_code=500)

    items, error = fetch_list(fn, result_key="items", policy=ListFetchPolicy.EMPTY_ON_404)
    assert items == []
    assert error is not None
    assert error.status_code == 500


def test_fetch_list_passes_through_args_and_kwargs():
    calls = []

    def fn(user_id, extra=None):
        calls.append((user_id, extra))
        return {"items": []}

    fetch_list(fn, "u1", result_key="items", extra="x")
    assert calls == [("u1", "x")]


def test_submit_with_image_retry_succeeds_first_try():
    result, error = submit_with_image_retry(
        submit_fn=lambda: {"bin": {"id": "1"}},
        ask_retry_fn=lambda bad_path: None,
        set_image_path_fn=lambda path: None,
    )
    assert result == {"bin": {"id": "1"}}
    assert error is None


def test_submit_with_image_retry_retries_once_then_succeeds():
    attempts = {"n": 0}
    paths_set = []

    def submit_fn():
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise ImageFileNotFoundError("/bad/path.png")
        return {"bin": {"id": "1"}}

    result, error = submit_with_image_retry(
        submit_fn=submit_fn,
        ask_retry_fn=lambda bad_path: "/good/path.png",
        set_image_path_fn=lambda path: paths_set.append(path),
    )
    assert result == {"bin": {"id": "1"}}
    assert error is None
    assert paths_set == ["/good/path.png"]
    assert attempts["n"] == 2


def test_submit_with_image_retry_gives_up_when_user_cancels_retry():
    def submit_fn():
        raise ImageFileNotFoundError("/bad/path.png")

    result, error = submit_with_image_retry(
        submit_fn=submit_fn,
        ask_retry_fn=lambda bad_path: None,  # user cancelled the retry prompt
        set_image_path_fn=lambda path: None,
    )
    assert result is None
    assert isinstance(error, ImageFileNotFoundError)


def test_submit_with_image_retry_does_not_retry_non_image_errors():
    def submit_fn():
        raise APIError("validation failed", status_code=400)

    result, error = submit_with_image_retry(
        submit_fn=submit_fn,
        ask_retry_fn=lambda bad_path: "/should/not/be/called.png",
        set_image_path_fn=lambda path: (_ for _ in ()).throw(
            AssertionError("should not be called for a non-image error")
        ),
    )
    assert result is None
    assert error.status_code == 400
