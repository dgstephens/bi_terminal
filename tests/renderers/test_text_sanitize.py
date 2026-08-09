"""The shared to_ascii_safe_bytes(), used by both renderers/petscii/
sanitize.py and renderers/atascii/sanitize.py — tested directly here once,
rather than duplicated per renderer."""

from bi_terminal.renderers._text_sanitize import to_ascii_safe_bytes


def test_em_dash():
    assert to_ascii_safe_bytes("Bin Inventory — 5 items") == b"Bin Inventory - 5 items"


def test_en_dash():
    assert to_ascii_safe_bytes("2020–2026") == b"2020-2026"


def test_smart_quotes():
    assert to_ascii_safe_bytes("it’s a “test”") == b"it's a \"test\""


def test_ellipsis():
    assert to_ascii_safe_bytes("loading…") == b"loading..."


def test_arrow():
    assert to_ascii_safe_bytes("a → b") == b"a -> b"


def test_plain_ascii_passes_through_unchanged():
    assert to_ascii_safe_bytes("plain ascii text 123!?") == b"plain ascii text 123!?"


def test_unknown_non_ascii_becomes_question_mark():
    result = to_ascii_safe_bytes("emoji: \U0001f600")
    assert result == b"emoji: ?"


def test_always_returns_bytes_never_raises():
    result = to_ascii_safe_bytes("☃☄★")  # snowman, comet, star — none mapped
    assert isinstance(result, bytes)
    assert result == b"???"
