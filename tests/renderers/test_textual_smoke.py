"""Placeholder for the Textual renderer's headless smoke test.

Not activated yet — renderers/textual/ has no renderer.py/app.py in this
increment (see README "Sequencing", step 2, the "tracer bullet": one screen
round-tripping end-to-end through a real TextualRenderer, which is the very
next piece of work, not part of this foundation increment). This file exists
now, skipped with a clear reason, so the test suite's shape already matches
what step 2 will fill in — a future session replaces the skip with a real
`from textual.testing import AppTest`-style headless pilot test exercising
`bi_terminal.renderers.textual.app`.
"""

import pytest


@pytest.mark.skip(
    reason="Textual renderer not yet built — see README Sequencing, step 2 (tracer bullet)"
)
def test_app_boots_and_shows_main_menu():
    pass
