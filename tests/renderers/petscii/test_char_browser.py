"""Unit tests for char_browser.py -- the PETSCII ground-truth diagnostic
tool (see its own module docstring for the full story: built 2026-08-12
after the tiered-detail image experiment shipped a wrong glyph-byte guess).

No real PetsciiIO/pty needed for most of this -- paginate() and
render_page_rows() are pure functions, and run()'s interactive loop is
exercised against a small in-memory fake with a scripted key queue, the
same style already used elsewhere in this project for io-free logic
testing. What these tests CANNOT verify (and don't try to): whether any
given byte value actually LOOKS like a particular glyph on a real screen --
that's the whole reason this tool exists, and is Daniel's own live-look
job, not something a unit test can stand in for.
"""

from bi_terminal.renderers.petscii import char_browser as cb
from bi_terminal.renderers.petscii import petscii_codes as pc


class _FakeIO:
    """Records every write_raw()/write_rows_paced() call and replays a
    scripted queue of read_key() return values -- enough surface for
    char_browser.run() to drive against, without a real PetsciiIO/pty at
    all. write_rows_paced() deliberately skips the real delay between rows
    (see PetsciiIO.write_rows_paced) -- these tests care about WHAT gets
    written, not the pacing itself, and a real per-row sleep would make
    this suite slow for no benefit; the pacing behavior itself is real
    PetsciiIO code, not re-tested here."""

    def __init__(self, keys):
        self._keys = list(keys)
        self.writes = []

    def write_raw(self, data: bytes) -> None:
        self.writes.append(data)

    def write_rows_paced(self, rows, delay=0.03) -> None:
        for row in rows:
            self.write_raw(row)

    def read_key(self, timeout=None):
        return self._keys.pop(0) if self._keys else "q"  # never hang a test

    def all_output(self) -> bytes:
        return b"".join(self.writes)


# ── KNOWN_CONTROL_BYTES / PRINTABLE_CANDIDATES ──────────────────────────


def test_known_control_bytes_includes_every_named_petscii_codes_constant_in_range():
    """Every single-byte constant petscii_codes.py defines THAT FALLS
    INSIDE the two control ranges must end up excluded -- the whole point
    of building this set dynamically instead of hardcoding a list and
    hoping nothing named gets added later without updating it too."""
    named_bytes_in_range = {
        getattr(pc, name)[0]
        for name in dir(pc)
        if not name.startswith("_") and isinstance(getattr(pc, name), bytes) and len(getattr(pc, name)) == 1
        if getattr(pc, name)[0] < 32 or 128 <= getattr(pc, name)[0] < 160
    }
    assert named_bytes_in_range  # sanity: petscii_codes.py does define some
    assert named_bytes_in_range <= cb.KNOWN_CONTROL_BYTES


def test_unverified_glyph_guess_constants_are_browsable_not_excluded():
    """Regression test for a real bug caught by this module's own test
    suite while writing it: an earlier version of KNOWN_CONTROL_BYTES
    treated EVERY named petscii_codes.py constant as a control code,
    unconditionally -- which silently excluded LEFT_HALF_BLOCK/
    LOWER_HALF_BLOCK/MEDIUM_SHADE/RIGHT_HALF_BLOCK (161/162/166/167) from
    the browse set. Those four are exactly the unverified glyph guesses
    this tool exists to check, not control codes to hide -- excluding them
    would have made the browser useless for the one thing it was built
    for."""
    for n in (161, 162, 166, 167):
        assert n not in cb.KNOWN_CONTROL_BYTES
        assert n in cb.PRINTABLE_CANDIDATES


def test_printable_candidates_excludes_both_control_ranges():
    for n in cb.PRINTABLE_CANDIDATES:
        assert not (0 <= n < 32)
        assert not (128 <= n < 160)


def test_printable_candidates_exact_count():
    # 256 total - 32 (0-31) - 32 (128-159) = 192.
    assert len(cb.PRINTABLE_CANDIDATES) == 192


def test_printable_candidates_no_duplicates_and_sorted():
    assert cb.PRINTABLE_CANDIDATES == sorted(set(cb.PRINTABLE_CANDIDATES))


# ── paginate() ───────────────────────────────────────────────────────────


def test_paginate_exact_multiple():
    assert cb.paginate(list(range(8)), page_size=4) == [[0, 1, 2, 3], [4, 5, 6, 7]]


def test_paginate_with_remainder():
    assert cb.paginate(list(range(10)), page_size=4) == [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9]]


def test_paginate_empty():
    assert cb.paginate([], page_size=4) == []


def test_paginate_real_candidates_page_count_and_last_page_size():
    pages = cb.paginate(cb.PRINTABLE_CANDIDATES)
    assert len(pages) == 4  # ceil(192 / 60)
    assert [len(p) for p in pages] == [60, 60, 60, 12]
    assert sum(len(p) for p in pages) == 192


# ── render_page_rows() ───────────────────────────────────────────────────


def test_render_page_rows_single_row_format():
    rows = cb.render_page_rows([65, 66, 67], columns=3)
    assert rows == [b" 65:A  66:B  67:C "]


def test_render_page_rows_splits_across_multiple_rows():
    rows = cb.render_page_rows([65, 66, 67], columns=2)
    assert rows == [b" 65:A  66:B ", b" 67:C "]


def test_render_page_rows_preserves_raw_glyph_byte_unmodified():
    """The whole point of this tool: byte 200 must appear as the literal
    byte 0xC8 in the output, completely unmodified -- no sanitize.py
    substitution, no case swap, nothing that could hide what it really is."""
    rows = cb.render_page_rows([200], columns=1)
    assert bytes([200]) in rows[0]


def test_render_page_rows_empty_input():
    assert cb.render_page_rows([]) == []


def test_render_page_rows_fits_40_column_screen():
    """Real protocol constraint (see renderer.py's _WIDTH convention) --
    a full 6-column row must not exceed 40 bytes."""
    rows = cb.render_page_rows(cb.PRINTABLE_CANDIDATES[: cb.COLUMNS], columns=cb.COLUMNS)
    assert len(rows[0]) <= 40


# ── build_page_lines() ───────────────────────────────────────────────────


def test_build_page_lines_contains_header_glyph_rows_and_footer():
    lines = cb.build_page_lines(0, 4, charset=1, byte_values=[65, 66, 67])
    joined = b"\r".join(lines)
    assert b"PETSCII CHAR BROWSER - CHARSET 1" in joined
    assert b"PAGE 1 OF 4" in joined
    assert b" 65:A" in joined
    assert b"[N]EXT [B]ACK [C]HARSET [Q]UIT" in joined


def test_build_page_lines_no_return_bytes_embedded():
    """build_page_lines() must not embed RETURN itself -- that's the
    caller's job (run() appends \\r per line before pacing), same
    conversion/display split petscii_art.py's image_to_petscii_rows() uses."""
    for line in cb.build_page_lines(0, 1, charset=1, byte_values=[65]):
        assert pc.RETURN not in line


# ── run() ────────────────────────────────────────────────────────────────


def test_run_uses_paced_writes_not_a_tight_unpaced_loop():
    """Real, live-reported bug (2026-08-12): the first version wrote every
    line as its own immediate write_raw() in a tight loop -- Daniel's real
    connection disconnected right after the first page rendered, before he
    ever pressed a key. Same failure shape as the earlier PETSCII image
    burst-write bug, same fix: route the page body through
    write_rows_paced() instead. This asserts run() actually calls the
    paced path, not just that the fake happens to produce equivalent
    output -- a regression here should fail even if a future FakeIO
    implementation changes."""
    calls = []
    io = _FakeIO(["q"])
    real_paced = io.write_rows_paced

    def _tracking_paced(rows, delay=0.03):
        calls.append(list(rows))
        real_paced(rows, delay)

    io.write_rows_paced = _tracking_paced
    cb.run(io)
    assert len(calls) == 1  # one page body written via the paced path
    assert len(calls[0]) > 1  # more than a single write -- the whole page body





def test_run_quits_on_q():
    io = _FakeIO(["q"])
    cb.run(io)  # must return, not hang or raise
    assert b"PETSCII CHAR BROWSER" in io.all_output()


def test_run_quits_on_escape():
    io = _FakeIO(["escape"])
    cb.run(io)


def test_run_quits_on_ctrl_c():
    io = _FakeIO(["ctrl+c"])
    cb.run(io)


def test_run_advances_page_then_quits():
    io = _FakeIO(["n", "q"])
    cb.run(io)
    out = io.all_output()
    assert b"PAGE 1 OF 4" in out
    assert b"PAGE 2 OF 4" in out


def test_run_wraps_forward_past_last_page():
    io = _FakeIO(["n", "n", "n", "n", "q"])  # 4 pages total -- wraps back to page 1
    cb.run(io)
    out = io.all_output()
    assert out.count(b"PAGE 1 OF 4") == 2  # initial draw + after wrapping


def test_run_back_wraps_to_last_page():
    io = _FakeIO(["b", "q"])  # back from page 1 wraps to the last page
    cb.run(io)
    out = io.all_output()
    assert b"PAGE 4 OF 4" in out


def test_run_charset_toggle_sends_switch_codes_and_updates_header():
    io = _FakeIO(["c", "q"])
    cb.run(io)
    out = io.all_output()
    assert pc.SWITCH_TO_LOWERCASE in out
    assert b"CHARSET 1" in out
    assert b"CHARSET 2" in out


def test_run_charset_toggle_back_sends_switch_to_uppercase():
    io = _FakeIO(["c", "c", "q"])
    cb.run(io)
    assert pc.SWITCH_TO_UPPERCASE in io.all_output()


def test_run_ignores_none_key_and_redraws_same_page():
    io = _FakeIO([None, None, "q"])
    cb.run(io)  # must not hang or crash on a timeout/no-key read
    assert io.all_output().count(b"PAGE 1 OF 4") == 3


def test_run_ignores_unrecognized_key():
    io = _FakeIO(["z", "q"])
    cb.run(io)  # unrecognized key -- just redraws, doesn't crash or misroute


def test_run_clears_screen_before_every_redraw():
    io = _FakeIO(["n", "q"])
    cb.run(io)
    assert io.writes.count(pc.CLR) == 2  # once for the initial page, once after 'n'
