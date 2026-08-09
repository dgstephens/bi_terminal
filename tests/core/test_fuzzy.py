from bi_terminal.core.fuzzy import fuzzy_match


def test_empty_query_matches_everything_at_index_zero():
    assert fuzzy_match("", "anything at all") == 0


def test_case_insensitive_substring_match():
    assert fuzzy_match("bin", "My BIN 3") == 3


def test_no_match_returns_none():
    assert fuzzy_match("xyz", "My Bin 3") is None


def test_earlier_match_has_lower_index():
    assert fuzzy_match("shelf", "Shelf A - Bin 3") == 0
    assert fuzzy_match("shelf", "Bin 3 - Shelf A") == 8


def test_not_fuzzy_subsequence_a_scattered_match_is_rejected():
    # Regression check for the exact false-positive bi_python's docstring
    # describes: "bin 3" should NOT match "Bin 25 ... Shelf 3" even though
    # the letters b-i-n...3 appear in order somewhere in that string — this
    # module does literal substring matching only, not fzf-style fuzzy.
    assert fuzzy_match("bin 3", "Bin 25 - Location: Shelf 3") is None
