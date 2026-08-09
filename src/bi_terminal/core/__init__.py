"""Renderer-agnostic core: data models, the API client, business logic.

Nothing in this package (or in bi_terminal.specs) may import a rendering
toolkit (textual, curses, etc.) — this is the single most important
architectural invariant of the whole project, enforced by
tests/test_layering.py. Every renderer, including doors with no GUI toolkit
at all, depends on this package; it must never depend back on any of them.
"""
