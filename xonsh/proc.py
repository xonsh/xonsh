"""xonsh.proc is deprecated"""
from xonsh.lazyasd import lazyobject
from xonsh.tools import print_warning


_WARNINGS_PRINTED = set()


def _print_proc_warning(msg):
    global _WARNINGS_PRINTED
    if msg not in _WARNINGS_PRINTED:
        print_warning(msg)
        _WARNINGS_PRINTED.add(msg)


_print_proc_warning(
    "The xonsh.proc module has been deprecated in favor of the "
    "xonsh.procs subpackage."
)


@lazyobject
def STDOUT_CAPTURE_KINDS():
    _print_proc_warning(
        "xonsh.proc.STDOUT_CAPTURE_KINDS has been deprecated. "
        "please use xonsh.procs.pipelines.STDOUT_CAPTURE_KINDS instead."
    )
    import xonsh.procs.pipelines

    return xonsh.procs.pipelines.STDOUT_CAPTURE_KINDS
