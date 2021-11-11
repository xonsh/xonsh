# setup import hooks
import xonsh.imphooks
import xonsh.execer
from xonsh.built_ins import XSH

# TODO: don't modify global state like this
if XSH.execer is None:
    XSH.load(execer=xonsh.execer.Execer())
xonsh.imphooks.install_import_hooks(XSH.execer)

del xonsh
