"""Tests for procs/readers.py — fd readers and utilities."""

import io
import os
import sys

import pytest

from xonsh.procs.readers import (
    BufferedFDParallelReader,
    NonBlockingFDReader,
    safe_fdclose,
)
from xonsh.pytest.tools import skip_if_on_windows


class TestNonBlockingFDReader:
    def test_read_all(self):
        r, w = os.pipe()
        os.write(w, b"hello world")
        os.close(w)
        reader = NonBlockingFDReader(r, timeout=0.1)
        data = reader.read()
        assert data == b"hello world"

    def test_readline(self):
        r, w = os.pipe()
        os.write(w, b"line1\nline2\n")
        os.close(w)
        reader = NonBlockingFDReader(r, timeout=0.1)
        lines = reader.readlines()
        assert b"line1\n" in lines
        assert b"line2\n" in lines

    def test_readlines(self):
        r, w = os.pipe()
        os.write(w, b"a\nb\nc\n")
        os.close(w)
        reader = NonBlockingFDReader(r, timeout=0.1)
        lines = reader.readlines()
        assert lines == [b"a\n", b"b\n", b"c\n"]

    def test_fileno(self):
        r, w = os.pipe()
        os.write(w, b"x")
        os.close(w)
        reader = NonBlockingFDReader(r, timeout=0.1)
        assert reader.fileno() == r
        reader.read()

    def test_readable(self):
        r, w = os.pipe()
        os.close(w)
        reader = NonBlockingFDReader(r, timeout=0.1)
        assert reader.readable() is True
        reader.read()

    def test_empty_pipe(self):
        r, w = os.pipe()
        os.close(w)
        reader = NonBlockingFDReader(r, timeout=0.1)
        assert reader.read() == b""


@skip_if_on_windows
class TestBufferedFDParallelReader:
    def test_read(self, tmp_path):
        p = tmp_path / "data.bin"
        p.write_bytes(b"buffered data")
        fd = os.open(str(p), os.O_RDONLY)
        reader = BufferedFDParallelReader(fd)
        reader.thread.join(timeout=2)
        os.close(fd)
        assert reader.buffer.getvalue() == b"buffered data"

    def test_custom_buffer(self, tmp_path):
        p = tmp_path / "data.bin"
        p.write_bytes(b"custom")
        fd = os.open(str(p), os.O_RDONLY)
        buf = io.BytesIO()
        reader = BufferedFDParallelReader(fd, buffer=buf)
        reader.thread.join(timeout=2)
        os.close(fd)
        assert buf.getvalue() == b"custom"


class TestSafeFdclose:
    def test_close_file_handle(self):
        f = open(os.devnull, "r")
        safe_fdclose(f)
        assert f.closed

    def test_close_none(self):
        safe_fdclose(None)  # no error

    def test_close_fd_int(self):
        r, w = os.pipe()
        os.close(w)
        safe_fdclose(r)
        with pytest.raises(OSError):
            os.fstat(r)

    def test_skip_stdin(self):
        safe_fdclose(sys.stdin)  # must not close stdin

    def test_skip_low_fd(self):
        safe_fdclose(0)  # must not close fd 0 (stdin)
        safe_fdclose(1)  # must not close fd 1 (stdout)
        safe_fdclose(2)  # must not close fd 2 (stderr)

    def test_cache(self):
        f = open(os.devnull, "r")
        cache = {}
        safe_fdclose(f, cache=cache)
        assert cache[f] is True
        # second call is a no-op
        safe_fdclose(f, cache=cache)
