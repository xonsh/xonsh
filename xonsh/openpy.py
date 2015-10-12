"""
Tools to open ``*.py`` files as Unicode, using the encoding specified within the
file, as per PEP 263.

Much of the code is taken from the tokenize module in Python 3.2.

This file was forked from the IPython project:

* Copyright (c) 2008-2014, IPython Development Team
* Copyright (C) 2001-2007 Fernando Perez <fperez@colorado.edu>
* Copyright (c) 2001, Janko Hauser <jhauser@zscout.de>
* Copyright (c) 2001, Nathaniel Gray <n8gray@caltech.edu>
"""
import io
import re
import os.path
from io import TextIOWrapper, BytesIO

from xonsh.tools import unicode_type

cookie_re = re.compile(r"coding[:=]\s*([-\w.]+)", re.UNICODE)
cookie_comment_re = re.compile(r"^\s*#.*coding[:=]\s*([-\w.]+)", re.UNICODE)

try:
    # Available in Python 3
    from tokenize import detect_encoding
except ImportError:
    from codecs import lookup, BOM_UTF8

    # Copied from Python 3.2 tokenize
    def _get_normal_name(orig_enc):
        """Imitates get_normal_name in tokenizer.c."""
        # Only care about the first 12 characters.
        enc = orig_enc[:12].lower().replace("_", "-")
        if enc == "utf-8" or enc.startswith("utf-8-"):
            return "utf-8"
        if enc in ("latin-1", "iso-8859-1", "iso-latin-1") or \
           enc.startswith(("latin-1-", "iso-8859-1-", "iso-latin-1-")):
            return "iso-8859-1"
        return orig_enc

    # Copied from Python 3.2 tokenize
    def detect_encoding(readline):
        """
        The detect_encoding() function is used to detect the encoding that
        should be used to decode a Python source file.  It requires one
        argment, readline, in the same way as the tokenize() generator.

        It will call readline a maximum of twice, and return the encoding used
        (as a string) and a list of any lines (left as bytes) it has read in.

        It detects the encoding from the presence of a utf-8 bom or an encoding
        cookie as specified in pep-0263.  If both a bom and a cookie are
        present, but disagree, a SyntaxError will be raised.  If the encoding
        cookie is an invalid charset, raise a SyntaxError.  Note that if a
        utf-8 bom is found, 'utf-8-sig' is returned.

        If no encoding is specified, then the default of 'utf-8' will be
        returned.
        """
        bom_found = False
        encoding = None
        default = 'utf-8'

        def read_or_stop():
            try:
                return readline()
            except StopIteration:
                return b''

        def find_cookie(line):
            try:
                line_string = line.decode('ascii')
            except UnicodeDecodeError:
                return None

            matches = cookie_re.findall(line_string)
            if not matches:
                return None
            encoding = _get_normal_name(matches[0])
            try:
                codec = lookup(encoding)
            except LookupError:
                # This behaviour mimics the Python interpreter
                raise SyntaxError("unknown encoding: " + encoding)

            if bom_found:
                if codec.name != 'utf-8':
                    # This behaviour mimics the Python interpreter
                    raise SyntaxError('encoding problem: utf-8')
                encoding += '-sig'
            return encoding

        first = read_or_stop()
        if first.startswith(BOM_UTF8):
            bom_found = True
            first = first[3:]
            default = 'utf-8-sig'
        if not first:
            return default, []

        encoding = find_cookie(first)
        if encoding:
            return encoding, [first]

        second = read_or_stop()
        if not second:
            return default, [first]

        encoding = find_cookie(second)
        if encoding:
            return encoding, [first, second]

        return default, [first, second]


try:
    # Available in Python 3.2 and above.
    from tokenize import tokopen
except ImportError:
    # Copied from Python 3.2 tokenize
    def tokopen(filename):
        """Open a file in read only mode using the encoding detected by
        detect_encoding().
        """
        buf = io.open(filename, 'rb')  # Tweaked to use io.open for Python 2
        encoding, lines = detect_encoding(buf.readline)
        buf.seek(0)
        text = TextIOWrapper(buf, encoding, line_buffering=True)
        text.mode = 'r'
        return text


def source_to_unicode(txt, errors='replace', skip_encoding_cookie=True):
    """Converts a bytes string with python source code to unicode.

    Unicode strings are passed through unchanged. Byte strings are checked
    for the python source file encoding cookie to determine encoding.
    txt can be either a bytes buffer or a string containing the source
    code.
    """
    if isinstance(txt, unicode_type):
        return txt
    if isinstance(txt, bytes):
        buf = BytesIO(txt)
    else:
        buf = txt
    try:
        encoding, _ = detect_encoding(buf.readline)
    except SyntaxError:
        encoding = "ascii"
    buf.seek(0)
    text = TextIOWrapper(buf, encoding, errors=errors, line_buffering=True)
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

# Code for going between .py files and cached .pyc files ----------------------

try:  # Python 3.2, see PEP 3147
    from imp import source_from_cache, cache_from_source  # pylint:disable=unused-import
except ImportError:
    # Python <= 3.1: .pyc files go next to .py
    def source_from_cache(path):
        basename, ext = os.path.splitext(path)
        if ext not in ('.pyc', '.pyo'):
            raise ValueError('Not a cached Python file extension', ext)
        # Should we look for .pyw files?
        return basename + '.py'

    def cache_from_source(path, debug_override=None):
        if debug_override is None:
            debug_override = __debug__
        basename, _ = os.path.splitext(path)
        return basename + '.pyc' if debug_override else '.pyo'
