"""Declarative, renderer-agnostic screen/flow specs.

Depends on bi_terminal.core only — never on bi_terminal.renderers (enforced by
tests/test_layering.py). Every screen in the app is described here as a plain
dataclass (see specs.base/specs.fields); each renderer consumes these specs in
its own idiom rather than the app being hand-coded per renderer.
"""
