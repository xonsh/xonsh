"""An interactive shell for the Jupyter kernel."""
import io
import sys
import builtins

from xonsh.base_shell import BaseShell


class StdJupyterRedirectBuf(io.RawIOBase):
    """Redirects standard I/O buffers to the Jupyter kernel."""

    def __init__(self, redirect):
        self.redirect = redirect
        self.encoding = redirect.encoding
        self.errors = redirect.errors

    def fileno(self):
        """Returns the file descriptor of the std buffer."""
        return self.redirect.fileno()

    def seek(self, offset, whence=io.SEEK_SET):
        """Sets the location in both the stdbuf and the membuf."""
        raise io.UnsupportedOperation("cannot seek Jupyter redirect")

    def truncate(self, size=None):
        """Truncate both buffers."""
        raise io.UnsupportedOperation("cannot truncate Jupyter redirect")

    def readinto(self, b):
        """Read bytes into buffer from both streams."""
        raise io.UnsupportedOperation("cannot read into Jupyter redirect")

    def write(self, b):
        """Write bytes to kernel."""
        s = b if isinstance(b, str) else b.decode(self.encoding, self.errors)
        self.redirect.write(s)


class StdJupyterRedirect(io.TextIOBase):
    """Redirects a standard I/O stream to the Jupyter kernel."""

    def __init__(self, name, kernel, parent_header=None):
        """
        Parameters
        ----------
        name : str
            The name of the buffer in the sys module, e.g. 'stdout'.
        kernel : XonshKernel
            Instance of a Jupyter kernel
        parent_header : dict or None, optional
            parent header information to pass along with the kernel
        """
        self._name = name
        self.kernel = kernel
        self.parent_header = parent_header

        self.std = getattr(sys, name)
        self.buffer = StdJupyterRedirectBuf(self)
        setattr(sys, name, self)

    @property
    def encoding(self):
        """The encoding of the stream"""
        env = builtins.__xonsh__.env
        return getattr(self.std, "encoding", env.get("XONSH_ENCODING"))

    @property
    def errors(self):
        """The encoding errors of the stream"""
        env = builtins.__xonsh__.env
        return getattr(self.std, "errors", env.get("XONSH_ENCODING_ERRORS"))

    @property
    def newlines(self):
        """The newlines of the standard buffer."""
        return self.std.newlines

    def _replace_std(self):
        std = self.std
        if std is None:
            return
        setattr(sys, self._name, std)
        self.std = None

    def __del__(self):
        self._replace_std()

    def close(self):
        """Restores the original std stream."""
        self._replace_std()

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.close()

    def write(self, s):
        """Writes data to the original kernel stream."""
        self.kernel._respond_in_chunks(self._name, s, parent_header=self.parent_header)

    def flush(self):
        """Flushes kernel iopub_stream."""
        self.kernel.iopub_stream.flush()

    def fileno(self):
        """Tunnel fileno() calls to the std stream."""
        return self.std.fileno()

    def seek(self, offset, whence=io.SEEK_SET):
        """Seek to a location."""
        raise io.UnsupportedOperation("cannot seek Jupyter redirect")

    def truncate(self, size=None):
        """Truncate the streams."""
        raise io.UnsupportedOperation("cannot truncate Jupyter redirect")

    def detach(self):
        """This operation is not supported."""
        raise io.UnsupportedOperation("cannot detach a Jupyter redirect")

    def read(self, size=None):
        """Read from the stream"""
        raise io.UnsupportedOperation("cannot read a Jupyter redirect")

    def readline(self, size=-1):
        """Read a line."""
        raise io.UnsupportedOperation("cannot read a line from a Jupyter redirect")


class JupyterShell(BaseShell):
    """A shell for the Jupyter kernel."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.kernel = None

    def default(self, line, kernel, parent_header=None):
        """Executes code, but redirects output to Jupyter client"""
        stdout = StdJupyterRedirect("stdout", kernel, parent_header)
        stderr = StdJupyterRedirect("stderr", kernel, parent_header)
        with stdout, stderr:
            rtn = super().default(line)
        return rtn
