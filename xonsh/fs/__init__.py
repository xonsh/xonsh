"""
Backported functions to implement the PEP 519 (Adding a file system path protocol) API.
"""

import abc
import sys
import io
import pathlib

try:
    from os import PathLike, fspath, fsencode, fsdecode
except ImportError:
    class PathLike(abc.ABC):
        """Abstract base class for implementing the file system path protocol."""

        @abc.abstractmethod
        def __fspath__(self):
            """Return the file system path representation of the object."""
            raise NotImplementedError

    PathLike.register(pathlib.Path)

    def fspath(path):
        """Return the string representation of the path.

        If str or bytes is passed in, it is returned unchanged. If __fspath__()
        returns something other than str or bytes then TypeError is raised. If
        this function is given something that is not str, bytes, or os.PathLike
        then TypeError is raised.
        """
        if isinstance(path, (str, bytes)):
            return path

        if isinstance(path, pathlib.Path):
            return str(path)

        # Work from the object's type to match method resolution of other magic
        # methods.
        path_type = type(path)
        try:
            path = path_type.__fspath__(path)
        except AttributeError:
            if hasattr(path_type, '__fspath__'):
                raise
        else:
            if isinstance(path, (str, bytes)):
                return path
            else:
                raise TypeError("expected __fspath__() to return str or bytes, "
                                "not " + type(path).__name__)

        raise TypeError("expected str, bytes or os.PathLike object, not "
                        + path_type.__name__)

    def _fscodec():
        encoding = sys.getfilesystemencoding()
        if encoding == 'mbcs':
            errors = 'strict'
        else:
            errors = 'surrogateescape'

        def fsencode(filename):
            """Encode filename (an os.PathLike, bytes, or str) to the filesystem
            encoding with 'surrogateescape' error handler, return bytes unchanged.
            On Windows, use 'strict' error handler if the file system encoding is
            'mbcs' (which is the default encoding).
            """
            filename = fspath(filename)  # Does type-checking of `filename`.
            if isinstance(filename, str):
                return filename.encode(encoding, errors)
            else:
                return filename

        def fsdecode(filename):
            """Decode filename (an os.PathLike, bytes, or str) from the filesystem
            encoding with 'surrogateescape' error handler, return str unchanged. On
            Windows, use 'strict' error handler if the file system encoding is
            'mbcs' (which is the default encoding).
            """
            filename = fspath(filename)  # Does type-checking of `filename`.
            if isinstance(filename, bytes):
                return filename.decode(encoding, errors)
            else:
                return filename

        return fsencode, fsdecode

    fsencode, fsdecode = _fscodec()
    del _fscodec

    def open(file, *pargs, **kwargs):
        if isinstance(file, PathLike):
            file = fspath(file)
        return io.open(file, *pargs, **kwargs)
