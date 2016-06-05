"""Hooks for the distributed parallel computing library."""

def _dworker(args, stdin=None):
    """Programatic access to the dworker utility, to allow launching
    workers that also have access to xonsh builtins.
    """
    from distributed.cli import dworker
    dworker.main.main(args=args, prog_name='dworker', standalone_mode=False)


aliases['dworker'] = _dworker

