import sys

import pytest

from xonsh.completers.tools import RichCompletion
from xonsh.pytest.tools import skip_if_on_windows
from xonsh.shells.readline_shell import (
    _ensure_newline,
    _parse_dsr_cursor_column,
    _render_completions,
)


@pytest.mark.parametrize(
    "prefix, completion, prefix_len, readline_completion",
    [
        ("", "a", 0, "a"),
        ("a", "b", 0, "ab"),
        ("a", "b", 1, "b"),
        ("adc", "bc", 2, "abc"),
        ("", RichCompletion("x", 0), 0, "x"),
        ("", RichCompletion("x", 0, "aaa", "aaa"), 0, "x"),
        ("a", RichCompletion("b", 1), 0, "b"),
        ("a", RichCompletion("b", 0), 1, "ab"),
        ("a", RichCompletion("b"), 0, "ab"),
        ("a", RichCompletion("b"), 1, "b"),
    ],
)
def test_render_completions(prefix, completion, prefix_len, readline_completion):
    assert _render_completions({completion}, prefix, prefix_len) == [
        readline_completion
    ]


def test_render_completions_filters_substring_matches():
    """Substring matches that would shrink readline's GCP must be filtered out.

    Regression test for https://github.com/xonsh/xonsh/issues/6209
    e.g. typing '@.imp.jso<Tab>' should not shrink to '@.imp.' because
    '_json' (a substring match) has a different prefix than 'json'.
    """
    prefix = "@.imp.jso"
    plen = 3  # replace last 3 chars ("jso")
    completions = {"json", "jsonrpc", "_json"}
    rendered = _render_completions(completions, prefix, plen)
    # _json renders to @.imp._json which does NOT start with @.imp.jso
    safe = [c for c in rendered if c.startswith(prefix)]
    assert all(c.startswith(prefix) for c in safe)
    assert "@.imp._json" not in safe
    assert "@.imp.json" in safe


@pytest.mark.parametrize(
    "resp, expected",
    [
        (b"\x1b[5;1R", 1),
        (b"\x1b[42;17R", 17),
        (b"\x1b[1;9999R", 9999),
        # trailing bytes after the R terminator are ignored
        (b"\x1b[5;1Rjunk", 1),
        # reply never closed with R
        (b"\x1b[5;1", None),
        # malformed: no semicolon
        (b"\x1b[5R", None),
        # non-numeric column
        (b"\x1b[5;xR", None),
        (b"", None),
    ],
)
def test_parse_dsr_cursor_column(resp, expected):
    assert _parse_dsr_cursor_column(resp) == expected


class _FakeStdin:
    """Stand-in for sys.stdin with a fileno — pytest's capture replaces
    the real stdin with a pseudofile that raises on fileno()."""

    def fileno(self):
        return 0


@pytest.fixture
def fake_tty(monkeypatch):
    """Mock out termios/tty/select IO so _ensure_newline is testable.

    The returned dict has a ``chunks`` list of byte strings delivered in
    order, one per select+read cycle.  Empty list means the terminal
    never replies.  Use ``capsys`` alongside to inspect what the function
    writes to stdout.
    """
    import termios

    state = {"chunks": []}
    monkeypatch.setattr(sys, "stdin", _FakeStdin())
    monkeypatch.setattr("os.isatty", lambda fd: True)
    monkeypatch.setattr(termios, "tcgetattr", lambda fd: object())
    monkeypatch.setattr(termios, "tcsetattr", lambda fd, when, attrs: None)
    monkeypatch.setattr("tty.setcbreak", lambda fd: None)

    def fake_select(rlist, wlist, xlist, timeout):
        if state["chunks"]:
            return (list(rlist), [], [])
        return ([], [], [])

    def fake_read(fd, n):
        return state["chunks"].pop(0)

    monkeypatch.setattr("select.select", fake_select)
    monkeypatch.setattr("os.read", fake_read)
    return state


@skip_if_on_windows
def test_ensure_newline_col_gt_1_prints_newline(fake_tty, capsys):
    fake_tty["chunks"] = [b"\x1b[5;42R"]
    _ensure_newline()
    assert capsys.readouterr().out == "\033[6n\n"


@skip_if_on_windows
def test_ensure_newline_col_1_does_not_print_newline(fake_tty, capsys):
    fake_tty["chunks"] = [b"\x1b[5;1R"]
    _ensure_newline()
    assert capsys.readouterr().out == "\033[6n"


@skip_if_on_windows
def test_ensure_newline_split_reply(fake_tty, capsys):
    """A DSR reply that arrives in several chunks must still be parsed.

    Regression test for issue #6344: reading via sys.stdin.read(1) would
    trap the tail of the reply in Python's TextIOWrapper buffer and leak
    it into the next input() call as phantom user input.
    """
    fake_tty["chunks"] = [b"\x1b[", b"5;", b"42R"]
    _ensure_newline()
    assert capsys.readouterr().out == "\033[6n\n"
    assert fake_tty["chunks"] == []  # entire reply consumed


@skip_if_on_windows
def test_ensure_newline_no_reply(fake_tty, capsys):
    fake_tty["chunks"] = []  # terminal never replies
    _ensure_newline()
    # DSR query still sent, but no newline emitted
    assert capsys.readouterr().out == "\033[6n"


@skip_if_on_windows
def test_ensure_newline_not_a_tty(monkeypatch, capsys):
    """Not a tty -> short-circuit before touching termios or stdout."""
    monkeypatch.setattr(sys, "stdin", _FakeStdin())
    monkeypatch.setattr("os.isatty", lambda fd: False)
    _ensure_newline()
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "line, exp",
    [
        [repr("hello"), "hello"],
        ["2 * 3", "6"],
    ],
)
def test_rl_prompt_cmdloop(line, exp, readline_shell, capsys):
    shell = readline_shell
    shell.use_rawinput = False
    shell.stdin.write(f"{line}\nexit\n")  # note: terminate with '\n'
    shell.stdin.seek(0)
    # ``exit`` now propagates SystemExit out of the loop (issue #6426); in
    # production ``main_xonsh`` catches it.
    with pytest.raises(SystemExit):
        shell.cmdloop()
    # xonsh, doesn't write all its output to shell.stdout
    # so capture sys.stdout
    out, err = capsys.readouterr()

    # sometimes the output has ansii color codes
    assert exp in out.strip()
