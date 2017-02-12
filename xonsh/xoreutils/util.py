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
