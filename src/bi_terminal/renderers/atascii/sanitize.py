"""Text sanitization for ATASCII output — thin re-export of the shared
implementation, matching renderers/petscii/sanitize.py's shape/naming
convention so the two renderers stay easy to compare side by side."""

from .._text_sanitize import to_ascii_safe_bytes as to_atascii_text

__all__ = ["to_atascii_text"]
