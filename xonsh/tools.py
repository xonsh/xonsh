"""Misc. xonsh tools.

The following implementations were forked from the IPython project:

* Copyright (c) 2008-2014, IPython Development Team
* Copyright (C) 2001-2007 Fernando Perez <fperez@colorado.edu>
* Copyright (c) 2001, Janko Hauser <jhauser@zscout.de>
* Copyright (c) 2001, Nathaniel Gray <n8gray@caltech.edu>

Implementations:

* decode()
* encode()
* cast_unicode()
* safe_hasattr()

"""
import sys

if sys.version_info[0] >= 3:
    string_types = (str, bytes)
    unicode_type = str
else:
    string_types = (str, unicode)
    unicode_type = unicode

DEFAULT_ENCODING = sys.getdefaultencoding()

def subproc_line(line):
    """Excapsulates a source code line in a uncaptured subprocess $[]."""
    tok = line.split(None, 1)[0]
    line = line.replace(tok, '$[' + tok, 1)
    if line.endswith('\n'):
        line += ']'
    else:
        len_nl = len(line)
        no_nl = line.rstrip('\n')
        line = no_nl + ']' + ('\n'*(len_nl-len(no_nl)))
    return line

def decode(s, encoding=None):
    encoding = encoding or DEFAULT_ENCODING
    return s.decode(encoding, "replace")

def encode(u, encoding=None):
    encoding = encoding or DEFAULT_ENCODING
    return u.encode(encoding, "replace")

def cast_unicode(s, encoding=None):
    if isinstance(s, bytes):
        return decode(s, encoding)
    return s

def safe_hasattr(obj, attr):
    """In recent versions of Python, hasattr() only catches AttributeError.
    This catches all errors.
    """
    try:
        getattr(obj, attr)
        return True
    except:
        return False

TERM_COLORS = {
    # Reset
    'NO_COLOR': '\001\033[0m\002',       # Text Reset
    # Regular Colors
    'BLACK': '\033[0;30m\002',        # BLACK
    'RED': '\001\033[0;31m\002',          # RED
    'GREEN': '\001\033[0;32m\002',        # GREEN
    'YELLOW': '\001\033[0;33m\002',       # YELLOW
    'BLUE': '\001\033[0;34m\002',         # BLUE
    'PURPLE': '\001\033[0;35m\002',       # PURPLE
    'CYAN': '\001\033[0;36m\002',         # CYAN
    'WHITE': '\001\033[0;37m\002',        # WHITE
    # Bold
    'BOLD_BLACK': '\001\033[1;30m\002',       # BLACK
    'BOLD_RED': '\001\033[1;31m\002',         # RED
    'BOLD_GREEN': '\001\033[1;32m\002',       # GREEN
    'BOLD_YELLOW': '\001\033[1;33m\002',      # YELLOW
    'BOLD_BLUE': '\001\033[1;34m\002',        # BLUE
    'BOLD_PURPLE': '\001\033[1;35m\002',      # PURPLE
    'BOLD_CYAN': '\001\033[1;36m\002',        # CYAN
    'BOLD_WHITE': '\001\033[1;37m\002',       # WHITE
    # Underline
    'UNDERLINE_BLACK': '\001\033[4;30m\002',       # BLACK
    'UNDERLINE_RED': '\001\033[4;31m\002',         # RED
    'UNDERLINE_GREEN': '\001\033[4;32m\002',       # GREEN
    'UNDERLINE_YELLOW': '\001\033[4;33m\002',      # YELLOW
    'UNDERLINE_BLUE': '\001\033[4;34m\002',        # BLUE
    'UNDERLINE_PURPLE': '\001\033[4;35m\002',      # PURPLE
    'UNDERLINE_CYAN': '\001\033[4;36m\002',        # CYAN
    'UNDERLINE_WHITE': '\001\033[4;37m\002',       # WHITE
    # Background
    'BACKGROUND_BLACK': '\001\033[40m\002',       # BLACK
    'BACKGROUND_RED': '\001\033[41m\002',         # RED
    'BACKGROUND_GREEN': '\001\033[42m\002',       # GREEN
    'BACKGROUND_YELLOW': '\001\033[43m\002',      # YELLOW
    'BACKGROUND_BLUE': '\001\033[44m\002',        # BLUE
    'BACKGROUND_PURPLE': '\001\033[45m\002',      # PURPLE
    'BACKGROUND_CYAN': '\001\033[46m\002',        # CYAN
    'BACKGROUND_WHITE': '\001\033[47m\002',       # WHITE
    # High Intensity
    'INTENSE_BLACK': '\001\033[0;90m\002',       # BLACK
    'INTENSE_RED': '\001\033[0;91m\002',         # RED
    'INTENSE_GREEN': '\001\033[0;92m\002',       # GREEN
    'INTENSE_YELLOW': '\001\033[0;93m\002',      # YELLOW
    'INTENSE_BLUE': '\001\033[0;94m\002',        # BLUE
    'INTENSE_PURPLE': '\001\033[0;95m\002',      # PURPLE
    'INTENSE_CYAN': '\001\033[0;96m\002',        # CYAN
    'INTENSE_WHITE': '\001\033[0;97m\002',       # WHITE
    # Bold High Intensity
    'BOLD_INTENSE_BLACK': '\001\033[1;90m\002',      # BLACK
    'BOLD_INTENSE_RED': '\001\033[1;91m\002',        # RED
    'BOLD_INTENSE_GREEN': '\001\033[1;92m\002',      # GREEN
    'BOLD_INTENSE_YELLOW': '\001\033[1;93m\002',     # YELLOW
    'BOLD_INTENSE_BLUE': '\001\033[1;94m\002',       # BLUE
    'BOLD_INTENSE_PURPLE': '\001\033[1;95m\002',     # PURPLE
    'BOLD_INTENSE_CYAN': '\001\033[1;96m\002',       # CYAN
    'BOLD_INTENSE_WHITE': '\001\033[1;97m\002',      # WHITE
    # High Intensity backgrounds
    'BACKGROUND_INTENSE_BLACK': '\001\033[0;100m\002',   # BLACK
    'BACKGROUND_INTENSE_RED': '\001\033[0;101m\002',     # RED
    'BACKGROUND_INTENSE_GREEN': '\001\033[0;102m\002',   # GREEN
    'BACKGROUND_INTENSE_YELLOW': '\001\033[0;103m\002',  # YELLOW
    'BACKGROUND_INTENSE_BLUE': '\001\033[0;104m\002',    # BLUE
    'BACKGROUND_INTENSE_PURPLE': '\001\033[0;105m\002',  # PURPLE
    'BACKGROUND_INTENSE_CYAN': '\001\033[0;106m\002',    # CYAN
    'BACKGROUND_INTENSE_WHITE': '\001\033[0;107m\002',   # WHITE
    }

# The following redirect classes were taken directly from Python 3.5's source 
# code (from the contextlib module). This can be removed when 3.5 is released, 
# although redirect_stdout exists in 3.4, redirect_stderr does not.
# See the Python software license: https://docs.python.org/3/license.html
# Copyright (c) Python Software Foundation. All rights reserved.
class _RedirectStream:

    _stream = None

    def __init__(self, new_target):
        self._new_target = new_target
        # We use a list of old targets to make this CM re-entrant
        self._old_targets = []

    def __enter__(self):
        self._old_targets.append(getattr(sys, self._stream))
        setattr(sys, self._stream, self._new_target)
        return self._new_target

    def __exit__(self, exctype, excinst, exctb):
        setattr(sys, self._stream, self._old_targets.pop())


class redirect_stdout(_RedirectStream):
    """Context manager for temporarily redirecting stdout to another file.

        # How to send help() to stderr
        with redirect_stdout(sys.stderr):
            help(dir)

        # How to write help() to a file
        with open('help.txt', 'w') as f:
            with redirect_stdout(f):
                help(pow)
    """
    _stream = "stdout"


class redirect_stderr(_RedirectStream):
    """Context manager for temporarily redirecting stderr to another file."""
    _stream = "stderr"
