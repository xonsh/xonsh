# amalgamate exclude
import os as _os

if _os.getenv("XONSH_NO_AMALGAMATE", ""):
    pass
else:
    import sys as _sys

    try:
        from xonsh.procs import __amalgam__

        readers = __amalgam__
        _sys.modules["xonsh.procs.readers"] = __amalgam__
        pipelines = __amalgam__
        _sys.modules["xonsh.procs.pipelines"] = __amalgam__
        posix = __amalgam__
        _sys.modules["xonsh.procs.posix"] = __amalgam__
        proxies = __amalgam__
        _sys.modules["xonsh.procs.proxies"] = __amalgam__
        specs = __amalgam__
        _sys.modules["xonsh.procs.specs"] = __amalgam__
        del __amalgam__
    except ImportError:
        pass
    del _sys
del _os
# amalgamate end
