"""Text sanitization for PETSCII output.

Moved to renderers/_text_sanitize.py once the ATASCII renderer needed the
exact same logic — this is a thin re-export (unchanged behavior, unchanged
import path) so nothing calling `to_petscii_text` needs to change.
"""

from .._text_sanitize import to_ascii_safe_bytes as to_petscii_text

__all__ = ["to_petscii_text"]
