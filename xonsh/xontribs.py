"""Tools for helping manage xontributions."""
import builtins
from argparse import ArgumentParser
from importlib import import_module
from importlib.util import find_spec, module_from_spec


def find_xontrib(name):
    """Finds a xontribution from its name."""
    if name.startswith('.'):
        spec = find_spec(name, package='xontrib')
    else:
        spec = find_spec('.' + name, package='xontrib')
    return spec or find_spec(name)


def xontrib_context(name):
    """Return a context dictionary for a xontrib of a given name."""
    spec = find_xontrib(name)
    m = import_module(spec.name)
    ctx = {k: getattr(m, k) for k in dir(m) if not k.startswith('_')}
    return ctx


def update_context(name, ctx=None):
    """Updates a context in place from a xontrib. If ctx is not provided,
    then __xonsh_ctx__ is updated.
    """
    if ctx is None:
        ctx = builtins.__xonsh_ctx__
    modctx = xontrib_context(name)
    return ctx.update(modctx)


def main(args, stdin=None):
    """Alias that loads xontribs"""
    # parse command line args
    parser = ArgumentParser(prog='xontrib',
                            description='loads xontribs - xonsh extensions')
    parser.add_argument('-v', '--verbose', action='store_true', default=False,
                        dest='verbose')
    parser.add_argument('names', nargs='+', default=(),
                        help='names of xontribs')
    ns = parser.parse_args(args)
    # load xontribs
    ctx = builtins.__xonsh_ctx__
    for name in ns.names:
        if ns.verbose:
            print('loading xontrib {0!r}'.format(name))
        update_context(name, ctx=ctx)
