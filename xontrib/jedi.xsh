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


@lazyobject
def jedi_version():
    if hasattr(jedi, "__version__"):
        return tuple(int(n) for n in jedi.__version__.split("."))
    else:
        return (0, 0, 0)


def complete_jedi(prefix, line, start, end, ctx):
    """Jedi-based completer for Python-mode."""
    if not HAS_JEDI:
        return set()
    new_api = jedi_version >= (0, 16, 0)
    src = builtins.__xonsh__.shell.shell.accumulated_inputs + line
    if new_api:
        script = jedi.api.Interpreter(src, [ctx])
    else:
        script = jedi.api.Interpreter(src, [ctx], column=end)
    script_comp = set()
    try:
        if new_api:
            script_comp = script.complete(column=end)
        else:
            script_comp = script.completions()
    except Exception:
        pass

    if builtins.__xonsh__.env.get('CASE_SENSITIVE_COMPLETIONS'):
        rtn = {x.name_with_symbols for x in script_comp
               if x.name_with_symbols.startswith(prefix)}
    else:
        rtn = {x.name_with_symbols for x in script_comp}
    return rtn


# register the completer
builtins.__xonsh__.ctx['complete_jedi'] = complete_jedi
completer add jedi complete_jedi end
completer remove python_mode
del builtins.__xonsh__.ctx['complete_jedi']
