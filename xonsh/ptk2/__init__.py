# provide backward compatibility for external xontribs till they can catch up.
import xonsh.ptk_shell.completer as completer
import xonsh.ptk_shell.history as history
import xonsh.ptk_shell.key_bindings as key_bindings
import xonsh.ptk_shell.shell as shell
import xonsh.ptk_shell as par

import sys

for m in [par, completer, history, key_bindings, shell]:
    sys.modules[m.__name__.replace('ptk_shell','ptk2')] = m


