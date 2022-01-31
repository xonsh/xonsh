"""Assorted utilities for xonsh core utils."""


def arg_handler(args, out, short, key, val, long=None):
    """A simple argument handler for xoreutils."""
    if short in args:
        args.remove(short)
        if isinstance(key, (list, tuple)):
            for k in key:
                out[k] = val
        else:
            out[key] = val
    if long is not None and long in args:
        args.remove(long)
        if isinstance(key, (list, tuple)):
            for k in key:
                out[k] = val
        else:
            out[key] = val


def run_alias(name: str, args=None):
    import sys

    from xonsh.built_ins import subproc_uncaptured
    from xonsh.main import setup
    from xonsh.xontribs import xontribs_load

    setup()

    xontribs_load(["coreutils"])
    args = sys.argv[1:] if args is None else args

    subproc_uncaptured([name] + args)
