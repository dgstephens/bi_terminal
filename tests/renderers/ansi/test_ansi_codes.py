"""Unit tests for the ANSI escape-code helpers, specifically the
background-color fix (real bug, live-reported 2026-08-10): NAVY_BG was
defined but never actually emitted anywhere, so the screen never showed the
intended navy background at all."""

from bi_terminal.renderers.ansi.ansi_codes import BASE_SGR, NAVY_BG, RESET, WHITE, colored, sgr


def test_base_sgr_sets_navy_background_and_white_foreground():
    assert BASE_SGR == sgr(NAVY_BG, WHITE)
    assert "44" in BASE_SGR  # NAVY_BG's actual SGR code
    assert "97" in BASE_SGR  # WHITE's actual SGR code


def test_colored_returns_to_base_sgr_not_a_hard_reset():
    """The real fix, not just cosmetic: a hard 0m reset after every colored
    span would drop the background back to the terminal's own default
    (usually black) for everything after the first colored() call anywhere
    on screen -- colored() must return to BASE_SGR (still navy) instead."""
    result = colored("hello", 96)
    assert result.endswith(BASE_SGR)
    assert RESET not in result


def test_reset_is_still_a_real_hard_reset_for_use_at_exit():
    """RESET itself must still exist and still mean a genuine full reset --
    it's deliberately used once, at the door's actual exit message, so the
    caller's own terminal isn't left tinted navy after they disconnect."""
    assert RESET == "\x1b[0m"
