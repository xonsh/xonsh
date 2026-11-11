"""Tests for ``xonsh.prompt.gitstatus`` helpers."""

from xonsh.prompt import gitstatus


def test_get_stash_count_with_non_ascii_messages(tmp_path):
    """Stash messages are counted without decoding them with the locale encoding."""
    stash_log = tmp_path / "logs" / "refs" / "stash"
    stash_log.parent.mkdir(parents=True)
    entry = "{} {} Łukasz <l@example.com> 1700000000 +0000\tOn main: {}\n"
    stash_log.write_bytes(
        (
            entry.format("0" * 40, "1" * 40, "Łukasz ✨")
            + entry.format("1" * 40, "2" * 40, "한글 메시지")
        ).encode()
    )
    assert gitstatus.get_stash_count(str(tmp_path)) == 2
