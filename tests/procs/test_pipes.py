"""Tests for PipeChannel fd management."""

import os

import pytest

from xonsh.procs.pipes import PipeChannel


def test_from_pipe_roundtrip():
    """Write through pipe, read back."""
    ch = PipeChannel.from_pipe()
    w = ch.open_writer()
    w.write(b"hello")
    w.flush()
    ch.close_writer()

    r = ch.open_reader()
    assert r.read() == b"hello"
    ch.close_reader()


def test_close_is_idempotent():
    ch = PipeChannel.from_pipe()
    ch.close_writer()
    ch.close_writer()  # no error
    ch.close_reader()
    ch.close_reader()  # no error


def test_open_writer_after_close_raises():
    ch = PipeChannel.from_pipe()
    ch.close()
    with pytest.raises(OSError, match="write end is closed"):
        ch.open_writer()


def test_open_reader_after_close_raises():
    ch = PipeChannel.from_pipe()
    ch.close()
    with pytest.raises(OSError, match="read end is closed"):
        ch.open_reader()


def test_fd_properties():
    ch = PipeChannel.from_pipe()
    assert isinstance(ch.read_fd, int)
    assert isinstance(ch.write_fd, int)
    assert ch.read_fd != ch.write_fd
    ch.close()
    assert ch.read_fd is None
    assert ch.write_fd is None


def test_close_frees_fds():
    ch = PipeChannel.from_pipe()
    r_fd, w_fd = ch.read_fd, ch.write_fd
    ch.close()
    # fds should be invalid now
    with pytest.raises(OSError):
        os.fstat(r_fd)
    with pytest.raises(OSError):
        os.fstat(w_fd)
