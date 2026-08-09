"""PIL -> ANSI-pixels / ASCII-art conversion, shared between the Textual
renderer's ansi/ascii image_mode and the future generic ANSI door renderer
(both target the same class of display — a truecolor-or-16-color terminal —
so there's no reason for the ANSI door to reimplement this from scratch once
it's built).

Ported verbatim from bi_python/forms.py::_image_to_renderable, populated now
during the Textual-renderer-rewrite phase (see README "Sequencing", step 3)
per the module's original reservation note.

PETSCII/ATASCII graphics conversion (C64 charset packing, Atari ANTIC/GTIA
modes) is NOT shared with this module — it's genuinely different code,
belonging in renderers/petscii/ and renderers/atascii/ respectively once that
work starts.
"""

from io import BytesIO


def image_to_renderable(url: str, mode: str):
    """Download *url* and return a Rich renderable suitable for a Static
    widget.

    Returns a Pixels object (mode "ansi"), an ASCII string (mode "ascii"),
    or None on any failure or when mode == "none".
    """
    if not url or mode == "none":
        return None
    try:
        import requests
        from PIL import Image

        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content)).convert("RGB")
        w = 60
        aspect = img.height / img.width

        if mode == "ansi":
            from rich_pixels import Pixels

            h = max(1, int(w * aspect * 1.0))
            return Pixels.from_image(img, resize=(w, h))

        elif mode == "ascii":
            import ascii_magic

            if hasattr(ascii_magic, "AsciiArt"):
                art = ascii_magic.AsciiArt.from_pillow_image(img)
                return art.to_ascii(columns=w)
            else:
                return ascii_magic.from_pillow_image(img)

    except Exception:
        return None
