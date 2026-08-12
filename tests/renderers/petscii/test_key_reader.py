"""PetsciiKeyReader tests — pipe-based, no tty dependency (the same code
path a real Standard I/O door process uses). Simpler than the ANSI
renderer's KeyReader tests since raw PETSCII has no multi-byte escape
sequences to disambiguate (confirmed against Synchronet's CTerm manual) —
every control code is exactly one byte."""

import os
import time

from bi_terminal.renderers.petscii.io import PetsciiKeyReader


def _keys(write_bytes: bytes, count: int):
    r_fd, w_fd = os.pipe()
    try:
        os.write(w_fd, write_bytes)
        reader = PetsciiKeyReader(r_fd)
        return [reader.read_key(timeout=1.0) for _ in range(count)]
    finally:
        os.close(r_fd)
        os.close(w_fd)


def test_plain_char():
    assert _keys(bytes([98]), 1) == ["b"]


def test_return_is_enter():
    assert _keys(bytes([13]), 1) == ["enter"]


def test_cursor_up_raw_petscii_spec():
    """145/17/157 (up/down/left, raw PETSCII spec) have no collision with
    Synchronet's translated codes -- stay live as a fallback for a
    hypothetical non-Synchronet-mediated raw PETSCII client."""
    assert _keys(bytes([145]), 1) == ["up"]


def test_cursor_down_raw_petscii_spec():
    assert _keys(bytes([17]), 1) == ["down"]


def test_cursor_left_raw_petscii_spec():
    assert _keys(bytes([157]), 1) == ["left"]


def test_cursor_right_synchronet_translated_wins_over_raw_spec():
    """Real, live-reported bug (2026-08-10/11), fixed via a careful
    one-key-at-a-time live capture through a real Synchronet+SyncTERM+
    Telnet connection: Synchronet translates cursor keys into a different
    byte set before an external Standard I/O door ever sees them. Byte 29
    is a genuine, confirmed collision -- raw PETSCII spec uses it for
    "right," Synchronet's translation uses the SAME byte for "left." Since
    every real deployment of this door runs behind Synchronet, Synchronet's
    meaning has to win: 29 must resolve to "left," not "right" -- this is
    the regression test for that specific, easy-to-get-backwards decision."""
    assert _keys(bytes([29]), 1) == ["left"]


def test_cursor_keys_synchronet_translated():
    """The other three Synchronet-translated codes, confirmed via the same
    live capture (down=0x0a, up=0x1e, right=0x06 -- right independently
    confirmed twice in that capture, same byte both times). None of these
    collide with the raw-spec fallback codes above (145/17/157)."""
    assert _keys(bytes([10]), 1) == ["down"]
    assert _keys(bytes([30]), 1) == ["up"]
    assert _keys(bytes([6]), 1) == ["right"]


def test_delete_is_backspace():
    assert _keys(bytes([20]), 1) == ["backspace"]


def test_ascii_backspace_is_also_backspace():
    """Real, live-reported bug (2026-08-11), confirmed via a real
    Synchronet+SyncTERM capture: what actually arrives for backspace/delete
    is 0x08 (ASCII backspace/Ctrl-H), not 20 (PETSCII's own documented
    DELETE code) -- confirmed by context in the raw log (appeared exactly
    where backspacing mid-email-address made sense), consistent across two
    independent real sessions. Without this, backspace presses were
    silently falling through to the plain-ASCII-decode branch and being
    typed as a literal \\x08 character instead of deleting anything."""
    assert _keys(bytes([8]), 1) == ["backspace"]


def test_escape_byte():
    assert _keys(bytes([0x1B]), 1) == ["escape"]


def test_ctrl_c():
    assert _keys(bytes([3]), 1) == ["ctrl+c"]


def test_tab():
    assert _keys(bytes([9]), 1) == ["tab"]


def test_two_plain_chars_queued():
    assert _keys(b"hi", 2) == ["h", "i"]


def test_digits_and_punctuation_pass_through():
    assert _keys(bytes([ord("5")]), 1) == ["5"]
    assert _keys(bytes([ord("-")]), 1) == ["-"]


def test_no_disambiguation_needed_unlike_ansi():
    """PETSCII has no CSI sequences at all -- a cursor key byte is
    immediately unambiguous, no peek/timeout needed to resolve it (contrast
    with renderers/ansi/io.py's KeyReader, which needs a 50ms peek after
    ESC). Verify this resolves essentially instantly."""
    r_fd, w_fd = os.pipe()
    try:
        os.write(w_fd, bytes([145]))
        reader = PetsciiKeyReader(r_fd)
        t0 = time.monotonic()
        result = reader.read_key(timeout=5.0)
        elapsed = time.monotonic() - t0
        assert result == "up"
        assert elapsed < 0.1
    finally:
        os.close(r_fd)
        os.close(w_fd)


def test_timeout_returns_none_without_hanging():
    r_fd, w_fd = os.pipe()
    try:
        reader = PetsciiKeyReader(r_fd)
        t0 = time.monotonic()
        result = reader.read_key(timeout=0.05)
        elapsed = time.monotonic() - t0
        assert result is None
        assert elapsed < 0.5
    finally:
        os.close(r_fd)
        os.close(w_fd)


def test_eof_on_closed_write_end():
    r_fd, w_fd = os.pipe()
    os.close(w_fd)
    try:
        reader = PetsciiKeyReader(r_fd)
        assert reader.read_key(timeout=0.5) is None
    finally:
        os.close(r_fd)


def test_unrecognized_high_control_byte_is_ignored_not_crashed():
    """A PETSCII control byte this reader doesn't have a mapping for (e.g.
    a color code arriving as bogus input) must be silently ignored, not
    raise -- followed by a real key to confirm the reader keeps working."""
    assert _keys(bytes([144]) + b"b", 2) == [None, "b"]


def test_debug_log_records_raw_byte_and_resolved_key(tmp_path):
    """New diagnostic capability (2026-08-10), added to investigate a real,
    live-reported bug: cursor keys + backspace not working through a real
    Synchronet BBS connection. Off by default (debug_log_path=None, the
    default in every other test in this file) -- this is the one test that
    actually exercises it."""
    log_path = tmp_path / "petscii_debug.log"
    r_fd, w_fd = os.pipe()
    try:
        os.write(w_fd, bytes([145, 20, 98]))  # up, backspace, "b"
        reader = PetsciiKeyReader(r_fd, debug_log_path=str(log_path))
        keys = [reader.read_key(timeout=1.0) for _ in range(3)]
        assert keys == ["up", "backspace", "b"]
        lines = log_path.read_text().splitlines()
        assert len(lines) == 3
        assert "raw=0x91 (145) -> 'up'" in lines[0]
        assert "raw=0x14 (20) -> 'backspace'" in lines[1]
        assert "raw=0x62 (98) -> 'b'" in lines[2]
    finally:
        os.close(r_fd)
        os.close(w_fd)


def test_debug_log_none_path_never_creates_a_file(tmp_path):
    """The off-by-default guarantee -- a debug feature that silently
    creates files nobody asked for would be its own bug."""
    would_be_log = tmp_path / "should_not_exist.log"
    assert _keys(b"b", 1) == ["b"]
    assert not would_be_log.exists()


# ── Telnet IAC negotiation handling ─────────────────────────────────────
# Real, live-reported bug (2026-08-12), root-caused via char_browser.py's
# own debug log: testing through SyncTERM's "Telnet" connection type sends
# real Telnet negotiation bytes the instant the connection opens, before
# any real keystroke. The exact live-captured sequence was 0xff 0xfb 0x03
# (IAC WILL SUPPRESS-GO-AHEAD) -- byte 3 happens to collide with this
# project's own Ctrl+C binding, so the negotiation handshake itself was
# silently "pressing Ctrl+C." See io.py's module-level IAC comment for the
# full story, including why this can't happen on a real Synchronet
# connection (only a bare-nc-bridge testing artifact).


def test_telnet_will_negotiation_is_not_treated_as_keystrokes():
    """The exact live-captured byte sequence that caused the reported bug,
    with nothing after it -- must resolve to a clean timeout (None), NOT
    'ctrl+c'. This is the direct regression test for the reported bug.
    Uses a short explicit timeout (not the shared _keys() helper's 1.0s)
    since there's genuinely nothing left to read after the sequence -- the
    call must actually wait out the timeout, and 1.0s per test adds up."""
    r_fd, w_fd = os.pipe()
    try:
        os.write(w_fd, bytes([255, 251, 3]))
        reader = PetsciiKeyReader(r_fd)
        assert reader.read_key(timeout=0.2) is None
    finally:
        os.close(r_fd)
        os.close(w_fd)


def test_telnet_will_negotiation_consumed_transparently_before_a_real_key():
    """A single read_key() call must skip straight past the whole
    negotiation sequence and return the very next real keystroke -- not
    three separate calls each returning something, which is what produced
    the reported "redraws 3 times" symptom."""
    assert _keys(bytes([255, 251, 3]) + b"b", 1) == ["b"]


def test_telnet_do_dont_wont_negotiation_also_consumed():
    for cmd in (252, 253, 254):  # WONT, DO, DONT
        assert _keys(bytes([255, cmd, 31]) + b"b", 1) == ["b"]


def test_telnet_iac_iac_escaped_data_byte_is_dropped():
    """IAC IAC is Telnet's own escape for a literal 0xFF data byte -- not
    a real keystroke either way (0xFF isn't ASCII-decodable), so it's
    correctly dropped rather than surfaced as anything."""
    assert _keys(bytes([255, 255]) + b"b", 1) == ["b"]


def test_telnet_subnegotiation_naws_is_consumed():
    """IAC SB NAWS <4 bytes width/height> IAC SE -- a real negotiation
    sequence a Telnet client can send unprompted (window size), bracketed
    by IAC SE rather than a fixed length. Must be fully consumed as one
    unit, not leak any of its bytes through as keystrokes."""
    naws_sequence = bytes([255, 250, 31, 0, 80, 0, 24, 255, 240])
    assert _keys(naws_sequence + b"b", 1) == ["b"]


def test_telnet_single_byte_command_is_consumed():
    """IAC NOP (241) -- a command with no option byte at all, the simplest
    shape (contrast with WILL/WONT/DO/DONT, which each need exactly one
    more byte consumed)."""
    assert _keys(bytes([255, 241]) + b"b", 1) == ["b"]


def test_telnet_negotiation_does_not_hang_when_truncated():
    """A malformed/truncated sequence (IAC WILL with the connection then
    going quiet, no option byte ever arriving) must resolve via the bounded
    per-byte timeout inside _consume_telnet_command, not hang forever."""
    r_fd, w_fd = os.pipe()
    try:
        os.write(w_fd, bytes([255, 251]))  # IAC WILL, then nothing
        reader = PetsciiKeyReader(r_fd)
        t0 = time.monotonic()
        result = reader.read_key(timeout=0.2)
        elapsed = time.monotonic() - t0
        assert result is None
        assert elapsed < 2.0  # bounded by _consume_telnet_command's own 1.0s ceiling
    finally:
        os.close(r_fd)
        os.close(w_fd)


def test_debug_log_records_telnet_iac_consumption(tmp_path):
    log_path = tmp_path / "petscii_debug.log"
    r_fd, w_fd = os.pipe()
    try:
        os.write(w_fd, bytes([255, 251, 3]) + b"b")
        reader = PetsciiKeyReader(r_fd, debug_log_path=str(log_path))
        assert reader.read_key(timeout=1.0) == "b"
        lines = log_path.read_text().splitlines()
        assert len(lines) == 2  # one IAC-consumed line, one for 'b'
        assert "TELNET-IAC" in lines[0]
        assert "raw=0x62 (98) -> 'b'" in lines[1]
    finally:
        os.close(r_fd)
        os.close(w_fd)
