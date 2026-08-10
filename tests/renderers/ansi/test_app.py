"""Unit test for AnsiApp's exit behavior — real bug, fixed 2026-08-10
alongside the background-color fix: the door's screens persist a navy
background across every colored() span while running, but a caller's own
terminal shouldn't stay tinted navy after they disconnect."""

import io as pyio

from bi_terminal.renderers.ansi.ansi_codes import RESET
from bi_terminal.renderers.ansi.app import _say_goodbye
from bi_terminal.renderers.ansi.io import AnsiIO


def test_say_goodbye_hard_resets_before_the_message():
    out = pyio.StringIO()
    io_obj = AnsiIO(0, out)  # fd unused for a write-only test
    _say_goodbye(io_obj)
    val = out.getvalue()
    assert val.startswith(RESET)
    assert "Goodbye!" in val
