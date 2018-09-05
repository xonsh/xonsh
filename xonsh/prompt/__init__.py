# amalgamate exclude
import os as _os

if _os.getenv("XONSH_DEBUG", ""):
    pass
else:
    import sys as _sys

    try:
        from xonsh.prompt import __amalgam__

        cwd = __amalgam__
        _sys.modules["xonsh.prompt.cwd"] = __amalgam__
        env = __amalgam__
        _sys.modules["xonsh.prompt.env"] = __amalgam__
        gitstatus = __amalgam__
        _sys.modules["xonsh.prompt.gitstatus"] = __amalgam__
        job = __amalgam__
        _sys.modules["xonsh.prompt.job"] = __amalgam__
        vc = __amalgam__
        _sys.modules["xonsh.prompt.vc"] = __amalgam__
        base = __amalgam__
        _sys.modules["xonsh.prompt.base"] = __amalgam__
        del __amalgam__
    except ImportError:
        pass
    del _sys
del _os
# amalgamate end
