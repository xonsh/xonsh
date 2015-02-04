"""Misc. xonsh tools."""

def subproc_line(line):
    """Excapsulates a line in a subprocess $()."""
    tok = line.split(None, 1)[0]
    line = line.replace(tok, '$(' + tok, 1) + ')'
    return line
