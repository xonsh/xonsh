# setup import hooks
import xonsh.imphooks
import xonsh.execer

execer = xonsh.execer.Execer()
xonsh.imphooks.install_import_hooks(execer)

del xonsh
