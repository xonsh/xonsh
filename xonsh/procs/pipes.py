"""Pipe channel for single-owner fd management."""

import os


class PipeChannel:
    """Single-owner pipe fd manager.
    Owner creates the pipe and is responsible for closing both ends.
    Consumers get non-owning wrappers via open_writer() / open_reader().
    One fd -- one os.close(). Creator closes. Consumers only borrow.
    """

    def __init__(self, read_fd, write_fd):
        self._read_fd = read_fd
        self._write_fd = write_fd

    @classmethod
    def from_pipe(cls):
        """Create a PipeChannel from os.pipe()."""
        r, w = os.pipe()
        return cls(r, w)

    @classmethod
    def from_pty(cls):
        """Create a PipeChannel from pty.openpty().

        Falls back to os.pipe() if PTY devices are exhausted.
        """
        import xonsh.lib.lazyimps as xli

        try:
            r, w = xli.pty.openpty()
        except OSError:
            r, w = os.pipe()
        return cls(r, w)

    @property
    def write_fd(self):
        return self._write_fd

    @property
    def read_fd(self):
        return self._read_fd

    def open_writer(self, mode="wb", buffering=-1):
        """Non-owning file wrapper for the write end."""
        return open(self._write_fd, mode, buffering=buffering, closefd=False)

    def open_reader(self, mode="rb", buffering=-1):
        """Non-owning file wrapper for the read end."""
        return open(self._read_fd, mode, buffering=buffering, closefd=False)

    def close_writer(self):
        """Close the write end fd. Idempotent and safe."""
        if self._write_fd is not None:
            try:
                os.close(self._write_fd)
            except OSError:
                pass
            self._write_fd = None

    def close_reader(self):
        """Close the read end fd. Idempotent and safe."""
        if self._read_fd is not None:
            try:
                os.close(self._read_fd)
            except OSError:
                pass
            self._read_fd = None

    def close(self):
        """Close both ends."""
        self.close_writer()
        self.close_reader()

    def __del__(self):
        """Safety net: close any fds that were not explicitly closed."""
        self.close()
