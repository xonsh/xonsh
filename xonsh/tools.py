"""Misc. xonsh tools."""
import sys

if sys.version_info[0] >= 3:
    string_types = (str, bytes)
else:
    string_types = (str, unicode)

def subproc_line(line):
    """Excapsulates a line in a subprocess $()."""
    tok = line.split(None, 1)[0]
    line = line.replace(tok, '$(' + tok, 1) + ')'
    return line
