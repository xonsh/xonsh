"""Jedi-based completer for Python-mode."""
import builtins
import importlib

from xonsh.lazyasd import lazyobject, lazybool


__all__ = ()


@lazybool
def HAS_JEDI():
    """``True`` if `jedi` is available, else ``False``."""
    spec = importlib.util.find_spec('jedi')
    return (spec is not None)


@lazyobject
def jedi():
    if HAS_JEDI:
        import jedi as m
    else:
        m = None
    return m


def complete_jedi(prefix, line, start, end, ctx):
    """Jedi-based completer for Python-mode."""
    if not HAS_JEDI:
        return set()
    src = builtins.__xonsh__.shell.shell.accumulated_inputs + line
    script = jedi.api.Interpreter(src, [ctx], column=end)
    if builtins.__xonsh__.env.get('CASE_SENSITIVE_COMPLETIONS'):
        rtn = {x.name_with_symbols for x in script.completions()
               if x.name_with_symbols.startswith(prefix)}
    else:
        rtn = {x.name_with_symbols for x in script.completions()}
    return rtn


# register the completer
builtins.__xonsh__.ctx['complete_jedi'] = complete_jedi
completer add jedi complete_jedi end
completer remove python_mode
del builtins.__xonsh__.ctx['complete_jedi']
