"""Misc. xonsh tools.

The following implementations were forked from the IPython project:

* Copyright (c) 2008-2014, IPython Development Team
* Copyright (C) 2001-2007 Fernando Perez <fperez@colorado.edu>
* Copyright (c) 2001, Janko Hauser <jhauser@zscout.de>
* Copyright (c) 2001, Nathaniel Gray <n8gray@caltech.edu>

Implemetations:

* decode()
* encode()
* cast_unicode()
* asfe_hasattr()

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
    """Excapsulates a line in a uncaptured subprocess $[]."""
    tok = line.split(None, 1)[0]
    line = line.replace(tok, '$[' + tok, 1) + ']'
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
    'NO_COLOR': '\033[0m',       # Text Reset
    # Regular Colors
    'BLACK': '\033[0;30m',        # BLACK
    'RED': '\033[0;31m',          # RED
    'GREEN': '\033[0;32m',        # GREEN
    'YELLOW': '\033[0;33m',       # YELLOW
    'BLUE': '\033[0;34m',         # BLUE
    'PURPLE': '\033[0;35m',       # PURPLE
    'CYAN': '\033[0;36m',         # CYAN
    'WHITE': '\033[0;37m',        # WHITE
    # Bold
    'BOLD_BLACK': '\033[1;30m',       # BLACK
    'BOLD_RED': '\033[1;31m',         # RED
    'BOLD_GREEN': '\033[1;32m',       # GREEN
    'BOLD_YELLOW': '\033[1;33m',      # YELLOW
    'BOLD_BLUE': '\033[1;34m',        # BLUE
    'BOLD_PURPLE': '\033[1;35m',      # PURPLE
    'BOLD_CYAN': '\033[1;36m',        # CYAN
    'BOLD_WHITE': '\033[1;37m',       # WHITE
    # Underline
    'UNDERLINE_BLACK': '\033[4;30m',       # BLACK
    'UNDERLINE_RED': '\033[4;31m',         # RED
    'UNDERLINE_GREEN': '\033[4;32m',       # GREEN
    'UNDERLINE_YELLOW': '\033[4;33m',      # YELLOW
    'UNDERLINE_BLUE': '\033[4;34m',        # BLUE
    'UNDERLINE_PURPLE': '\033[4;35m',      # PURPLE
    'UNDERLINE_CYAN': '\033[4;36m',        # CYAN
    'UNDERLINE_WHITE': '\033[4;37m',       # WHITE
    # Background
    'BACKGROUND_BLACK': '\033[40m',       # BLACK
    'BACKGROUND_RED': '\033[41m',         # RED
    'BACKGROUND_GREEN': '\033[42m',       # GREEN
    'BACKGROUND_YELLOW': '\033[43m',      # YELLOW
    'BACKGROUND_BLUE': '\033[44m',        # BLUE
    'BACKGROUND_PURPLE': '\033[45m',      # PURPLE
    'BACKGROUND_CYAN': '\033[46m',        # CYAN
    'BACKGROUND_WHITE': '\033[47m',       # WHITE
    # High Intensity
    'INTENSE_BLACK': '\033[0;90m',       # BLACK
    'INTENSE_RED': '\033[0;91m',         # RED
    'INTENSE_GREEN': '\033[0;92m',       # GREEN
    'INTENSE_YELLOW': '\033[0;93m',      # YELLOW
    'INTENSE_BLUE': '\033[0;94m',        # BLUE
    'INTENSE_PURPLE': '\033[0;95m',      # PURPLE
    'INTENSE_CYAN': '\033[0;96m',        # CYAN
    'INTENSE_WHITE': '\033[0;97m',       # WHITE
    # Bold High Intensity
    'BOLD_INTENSE_BLACK': '\033[1;90m',      # BLACK
    'BOLD_INTENSE_RED': '\033[1;91m',        # RED
    'BOLD_INTENSE_GREEN': '\033[1;92m',      # GREEN
    'BOLD_INTENSE_YELLOW': '\033[1;93m',     # YELLOW
    'BOLD_INTENSE_BLUE': '\033[1;94m',       # BLUE
    'BOLD_INTENSE_PURPLE': '\033[1;95m',     # PURPLE
    'BOLD_INTENSE_CYAN': '\033[1;96m',       # CYAN
    'BOLD_INTENSE_WHITE': '\033[1;97m',      # WHITE
    # High Intensity backgrounds
    'BACKGROUND_INTENSE_BLACK': '\033[0;100m',   # BLACK
    'BACKGROUND_INTENSE_RED': '\033[0;101m',     # RED
    'BACKGROUND_INTENSE_GREEN': '\033[0;102m',   # GREEN
    'BACKGROUND_INTENSE_YELLOW': '\033[0;103m',  # YELLOW
    'BACKGROUND_INTENSE_BLUE': '\033[0;104m',    # BLUE
    'BACKGROUND_INTENSE_PURPLE': '\033[0;105m',  # PURPLE
    'BACKGROUND_INTENSE_CYAN': '\033[0;106m',    # CYAN
    'BACKGROUND_INTENSE_WHITE': '\033[0;107m',   # WHITE
    }
