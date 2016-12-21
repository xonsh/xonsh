import importlib.util
import os.path
import xonsh.tools as xt

_XCX_MODULES = []


def _xcx_load_complete_modules():
    dir_ = xt.expanduser_abs_path('~/.xonsh/completers')
    if not os.path.isdir(dir_):
        return
    for f in os.listdir(dir_):
        if not f.endswith('.py'):
            continue
        full_path = os.path.join(dir_, f)
        if not os.path.isfile(full_path):
            continue
        name = f.split('.')[0]
        spec = importlib.util.spec_from_file_location(
            "xonsh.completers.xonsh_{}".format(name), full_path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _XCX_MODULES.append(m)


def complete_xonsh(prefix, line, begidx, endidx, ctx):
    try:
        cmd = line.strip().split()[0]
    except IndexError:
        return
    if not cmd:
        return
    for m in _XCX_MODULES:
        if not m.__name__.endswith(cmd):
            continue
        result = m.complete(prefix, line, begidx, endidx, ctx)
        if result is not None:
            return result
    return


_xcx_load_complete_modules()
