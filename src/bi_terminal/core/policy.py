"""Shared decision policies that bi_python implemented inconsistently as four
separate ad-hoc try/except blocks scattered across app.py.

Confirmed against bi_python's actual source (not just paraphrase) before this
module was written:

- bins_menu / all_items_menu: 404 from get_bins_by_user / get_items_by_user
  treated as "empty list" (new account, zero items yet) — correct — but any
  OTHER error (auth failure, network, 5xx) notifies and aborts. Good policy.
- items_in_bin_menu: get_items_by_bin has NO 404 special-case at all — any
  error, including a plain "this bin has zero items" 404, aborts into a dead
  menu. A bin with zero items should behave like "My Items" with zero items,
  not error out. Bug.
- shared_bins_menu / shared_bin_items_view: swallow ALL APIErrors (any status
  code) to an empty list. A genuine network blip or auth failure on shared
  bins silently renders as "you have no bins shared with you," which is
  actively misleading.

Fixed here by normalizing every list-fetch call site onto ONE named policy —
EMPTY_ON_404 — via fetch_list(). This is a real behavior change for the
shared-bins call sites (they now surface non-404 errors instead of hiding
them) — flagged explicitly in the project plan as worth a second look during
Textual-renderer parity testing, not something to silently ship unnoticed.
"""

from enum import Enum
from typing import Callable, List, Optional, Tuple

from .errors import APIError, ImageFileNotFoundError


class ListFetchPolicy(Enum):
    EMPTY_ON_404 = "empty_on_404"
    """A 404 means "nothing yet" (e.g. a brand-new account, or a bin with no
    items) and should render as an empty list, not an error. Any other status
    code is a real failure and should still surface as an error. This is the
    ONE policy every list-fetch call site in bi_terminal uses — see module
    docstring for why the other two policies bi_python used were both wrong
    in different directions."""


def fetch_list(
    fn: Callable[..., dict],
    *args,
    result_key: str,
    policy: ListFetchPolicy = ListFetchPolicy.EMPTY_ON_404,
    **kwargs,
) -> Tuple[list, Optional[APIError]]:
    """Call fn(*args, **kwargs) (a core.api.BinInventoryAPI list method),
    extract data[result_key], and apply `policy` to error handling.

    Returns (items, error). `error` is None on success (including the
    "empty on 404" case — a 404 handled by policy is NOT an error to
    display). When `error` is not None, the caller should notify the user
    and treat `items` (always []) as unusable, matching bi_python's existing
    "notify + return/abort" behavior for genuine failures.
    """
    try:
        data = fn(*args, **kwargs)
        return list(data.get(result_key) or []), None
    except APIError as e:
        if policy == ListFetchPolicy.EMPTY_ON_404 and e.status_code == 404:
            return [], None
        return [], e


def submit_with_image_retry(
    submit_fn: Callable[[], dict],
    ask_retry_fn: Callable[[str], Optional[str]],
    set_image_path_fn: Callable[[str], None],
) -> Tuple[Optional[dict], Optional[APIError]]:
    """Runs submit_fn() (a core.api create/update call closed over the
    current form state), retrying the whole submit if it fails because a
    locally-supplied image path doesn't exist on disk.

    On ImageFileNotFoundError: calls ask_retry_fn(bad_path) to get a
    replacement path from the user (renderer-supplied — e.g. a text-prompt
    screen). If ask_retry_fn returns a falsy value (user cancelled the
    retry), gives up and returns (None, the original error). Otherwise calls
    set_image_path_fn(new_path) to mutate the closed-over form state that
    submit_fn will read on its next call, and retries.

    Any other APIError is NOT retried — returned immediately as the second
    tuple element, matching bi_python's original "only image-not-found gets a
    retry loop, everything else aborts" behavior. Unlike bi_python, this is
    now used uniformly by ALL four forms (bin/item/profile) — bi_python's
    edit_profile lacked this loop entirely, a confirmed inconsistency fixed
    here since the mechanism is shared.

    On success: returns (response_dict, None).
    """
    while True:
        try:
            return submit_fn(), None
        except ImageFileNotFoundError as e:
            new_path = ask_retry_fn(e.path)
            if not new_path:
                return None, e
            set_image_path_fn(new_path)
        except APIError as e:
            return None, e
