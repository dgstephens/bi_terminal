"""The dismiss-value contract's sentinels: CANCELLED and EMPTY_SUBMIT must be
distinct from each other, from None, and from any real value a renderer might
legitimately return (e.g. an empty string) — that's the whole point of using
named sentinel objects instead of overloading None/"" for two different
meanings, per specs.base's docstrings."""

from bi_terminal.specs.base import CANCELLED, EMPTY_SUBMIT
from bi_terminal.specs.fields import TextPromptSpec


def test_sentinels_are_distinct_from_each_other():
    assert CANCELLED is not EMPTY_SUBMIT
    assert CANCELLED != EMPTY_SUBMIT


def test_sentinels_are_distinct_from_none_and_empty_string():
    assert CANCELLED is not None
    assert EMPTY_SUBMIT is not None
    assert CANCELLED != ""
    assert EMPTY_SUBMIT != ""
    assert CANCELLED != []
    assert EMPTY_SUBMIT != []


def test_sentinels_are_stable_singletons():
    # Re-importing must yield the same objects (not re-constructed each time)
    # — renderers/tests compare with `is`, not `==`.
    from bi_terminal.specs.base import CANCELLED as c2
    from bi_terminal.specs.base import EMPTY_SUBMIT as e2

    assert CANCELLED is c2
    assert EMPTY_SUBMIT is e2


def test_sentinel_repr_is_readable_for_test_failure_output():
    assert "CANCELLED" in repr(CANCELLED)
    assert "EMPTY_SUBMIT" in repr(EMPTY_SUBMIT)


def test_text_prompt_spec_distinguish_empty_submit_defaults_false():
    spec = TextPromptSpec(prompt="Search")
    assert spec.distinguish_empty_submit is False


def test_text_prompt_spec_can_opt_into_distinguishing_empty_submit():
    spec = TextPromptSpec(prompt="Search", distinguish_empty_submit=True)
    assert spec.distinguish_empty_submit is True
