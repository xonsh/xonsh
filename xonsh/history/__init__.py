# amalgamate exclude
import os as _os

if _os.getenv("XONSH_DEBUG", ""):
    pass
else:
    import sys as _sys

    try:
        from xonsh.history import __amalgam__

        base = __amalgam__
        _sys.modules["xonsh.history.base"] = __amalgam__
        dummy = __amalgam__
        _sys.modules["xonsh.history.dummy"] = __amalgam__
        json = __amalgam__
        _sys.modules["xonsh.history.json"] = __amalgam__
        sqlite = __amalgam__
        _sys.modules["xonsh.history.sqlite"] = __amalgam__
        main = __amalgam__
        _sys.modules["xonsh.history.main"] = __amalgam__
        del __amalgam__
    except ImportError:
        pass
    del _sys
del _os
# amalgamate end
