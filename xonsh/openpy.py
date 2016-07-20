# -*- coding: utf-8 -*-
"""Tools to open ``*.py`` files as Unicode.

Uses the encoding specified within the file, as per PEP 263.

Much of the code is taken from the tokenize module in Python 3.2.

This file was forked from the IPython project:

* Copyright (c) 2008-2014, IPython Development Team
* Copyright (C) 2001-2007 Fernando Perez <fperez@colorado.edu>
* Copyright (c) 2001, Janko Hauser <jhauser@zscout.de>
* Copyright (c) 2001, Nathaniel Gray <n8gray@caltech.edu>
"""
import io
import re

from xonsh.lazyasd import LazyObject
from xonsh.tokenize import detect_encoding, tokopen


cookie_comment_re = LazyObject(
    lambda: re.compile(r"^\s*#.*coding[:=]\s*([-\w.]+)", re.UNICODE),
    globals(), 'cookie_comment_re')


def source_to_unicode(txt, errors='replace', skip_encoding_cookie=True):
    """Converts a bytes string with python source code to unicode.

    Unicode strings are passed through unchanged. Byte strings are checked
    for the python source file encoding cookie to determine encoding.
    txt can be either a bytes buffer or a string containing the source
    code.
    """
    if isinstance(txt, str):
        return txt
    if isinstance(txt, bytes):
        buf = io.BytesIO(txt)
    else:
        buf = txt
    try:
        encoding, _ = detect_encoding(buf.readline)
    except SyntaxError:
        encoding = "ascii"
    buf.seek(0)
    text = io.TextIOWrapper(buf, encoding, errors=errors, line_buffering=True)
    text.mode = 'r'
    if skip_encoding_cookie:
        return u"".join(strip_encoding_cookie(text))
    else:
        return text.read()


def strip_encoding_cookie(filelike):
    """Generator to pull lines from a text-mode file, skipping the encoding
    cookie if it is found in the first two lines.
    """
    it = iter(filelike)
    try:
        first = next(it)
        if not cookie_comment_re.match(first):
            yield first
        second = next(it)
        if not cookie_comment_re.match(second):
            yield second
    except StopIteration:
        return
    for line in it:
        yield line


def read_py_file(filename, skip_encoding_cookie=True):
    """Read a Python file, using the encoding declared inside the file.

    Parameters
    ----------
    filename : str
      The path to the file to read.
    skip_encoding_cookie : bool
      If True (the default), and the encoding declaration is found in the first
      two lines, that line will be excluded from the output - compiling a
      unicode string with an encoding declaration is a SyntaxError in Python 2.

    Returns
    -------
    A unicode string containing the contents of the file.
    """
    with tokopen(filename) as f:  # the open function defined in this module.
        if skip_encoding_cookie:
            return "".join(strip_encoding_cookie(f))
        else:
            return f.read()


def read_py_url(url, errors='replace', skip_encoding_cookie=True):
    """Read a Python file from a URL, using the encoding declared inside the file.

    Parameters
    ----------
    url : str
      The URL from which to fetch the file.
    errors : str
      How to handle decoding errors in the file. Options are the same as for
      bytes.decode(), but here 'replace' is the default.
    skip_encoding_cookie : bool
      If True (the default), and the encoding declaration is found in the first
      two lines, that line will be excluded from the output - compiling a
      unicode string with an encoding declaration is a SyntaxError in Python 2.

    Returns
    -------
    A unicode string containing the contents of the file.
    """
    # Deferred import for faster start
    try:
        from urllib.request import urlopen  # Py 3
    except ImportError:
        from urllib import urlopen
    response = urlopen(url)
    buf = io.BytesIO(response.read())
    return source_to_unicode(buf, errors, skip_encoding_cookie)


def _list_readline(x):
    """Given a list, returns a readline() function that returns the next element
    with each call.
    """
    x = iter(x)

    def readline():
        return next(x)

    return readline
