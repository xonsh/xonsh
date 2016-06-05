"""Hooks for the distributed parallel computing library."""

def _dworker(args, stdin=None):
    """Programatic access to the dworker utility, to allow launching
    workers that also have access to xonsh builtins.
    """
    pass


aliases['dworker'] = _dworker