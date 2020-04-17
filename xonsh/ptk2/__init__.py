# provide backward compatibility for external xontribs till they can catch up.

import importlib
import pkgutil
import sys

src_pkg = "xonsh.ptk_shell"

src_pkg_imp = importlib.import_module(src_pkg)

# clone package, and original __name__ (!), to my own module entry
sys.modules[__name__] = src_pkg_imp

# create module entries for all submodules
for mi in pkgutil.iter_modules(src_pkg_imp.__path__):
    sys.modules[__name__ + "." + mi.name] = importlib.import_module(
        src_pkg + "." + mi.name
    )
