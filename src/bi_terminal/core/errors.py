"""Typed exceptions for the core API layer.

bi_python's api.py raised a plain APIError with the string message
"Image file not found: {path}" for a missing local image file, and every
caller (create_bin/edit_bin/create_item/edit_item in bi_python's app.py)
detected that specific case by string-matching
`str(e).startswith("Image file not found")`. That's fragile — any renderer
reimplementing the same retry-on-missing-image flow would have to duplicate
the exact string. Fixed here with a real subclass; core/api.py raises it,
callers catch it by type.
"""


class APIError(Exception):
    """Raised for any non-2xx response from the Binventory backend."""

    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = status_code


class ImageFileNotFoundError(APIError):
    """A locally-supplied image path (bin/item/profile image upload) doesn't
    exist on disk. Distinct from a backend-side APIError so callers can offer
    a "re-enter the path" retry loop instead of aborting the whole submit."""

    def __init__(self, path: str):
        super().__init__(f"Image file not found: {path}", status_code=0)
        self.path = path
