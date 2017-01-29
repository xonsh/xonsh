"""Jedi-based completer for Python-mode."""
import builtins

import xonsh.platform as xp
import xonsh.lazyimps as xlimps


def complete_jedi(prefix, line, start, end, ctx):
    """Jedi-based completer for Python-mode."""
    if not xp.HAS_JEDI:
        return set()
    script = xlimps.jedi.api.Interpreter(line, [ctx], column=end)
    if builtins.__xonsh_env__.get('CASE_SENSITIVE_COMPLETIONS'):
        rtn = {x.name_with_symbols for x in script.completions()
               if x.name_with_symbols.startswith(prefix)}
    else:
        rtn = {x.name_with_symbols for x in script.completions()}
    return rtn
