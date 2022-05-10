# amalgamate exclude
import os as _os

if _os.getenv("XONSH_NO_AMALGAMATE", ""):
    pass
else:
    import sys as _sys

    try:
        from xonsh.completers import __amalgam__

        bash_completion = __amalgam__
        _sys.modules["xonsh.completers.bash_completion"] = __amalgam__
        dirs = __amalgam__
        _sys.modules["xonsh.completers.dirs"] = __amalgam__
        tools = __amalgam__
        _sys.modules["xonsh.completers.tools"] = __amalgam__
        bash = __amalgam__
        _sys.modules["xonsh.completers.bash"] = __amalgam__
        commands = __amalgam__
        _sys.modules["xonsh.completers.commands"] = __amalgam__
        completer = __amalgam__
        _sys.modules["xonsh.completers.completer"] = __amalgam__
        environment = __amalgam__
        _sys.modules["xonsh.completers.environment"] = __amalgam__
        imports = __amalgam__
        _sys.modules["xonsh.completers.imports"] = __amalgam__
        man = __amalgam__
        _sys.modules["xonsh.completers.man"] = __amalgam__
        path = __amalgam__
        _sys.modules["xonsh.completers.path"] = __amalgam__
        python = __amalgam__
        _sys.modules["xonsh.completers.python"] = __amalgam__
        _aliases = __amalgam__
        _sys.modules["xonsh.completers._aliases"] = __amalgam__
        base = __amalgam__
        _sys.modules["xonsh.completers.base"] = __amalgam__
        init = __amalgam__
        _sys.modules["xonsh.completers.init"] = __amalgam__
        del __amalgam__
    except ImportError:
        pass
    del _sys
del _os
# amalgamate end
