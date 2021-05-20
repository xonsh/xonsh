"""
This adds `xog` - a simple command to establish and print temporary traceback log file.
"""

import os
import pathlib
import tempfile

from xonsh.built_ins import XSH

__all__ = ()


def _get_log_file_name():
    return pathlib.Path(f"{tempfile.gettempdir()}/xonsh-{os.getpid()}.log")


def _clear_log(logfile, stderr):
    try:
        os.remove(logfile)
    except OSError as e:
        print(f"xog: {e}", file=stderr)
        return False
    return True


def _print_log(logfile, stdout, stderr):
    try:
        with open(logfile) as log:
            for line in log:
                print(line, end="", file=stdout)
    except OSError as e:
        print(f"xog: {e}", file=stderr)
        return False
    return True


def _print_help(stdout):
    print(
        """Usage: xog [OPTIONS]
Prints contents of the shell's traceback log file.

Options:
  -c, --clear\t\tclear the log file contents
  -?, --help\t\tprint this help text
"""
    )


def _xog(args, stdout=None, stderr=None):
    if "-?" in args or "--help" in args:
        _print_help(stdout)
        return 0

    logfile = XSH.env.get("XONSH_TRACEBACK_LOGFILE", "")
    if not (logfile and os.path.isfile(logfile)):
        print("Traceback log file doesn't exist.", file=stderr)
        return -1

    if "-c" in args or "--clear" in args:
        rc = _clear_log(logfile, stderr=stderr)
        return 0 if rc else -1

    rc = _print_log(logfile, stdout, stderr)
    return 0 if rc else -1


XSH.env["XONSH_TRACEBACK_LOGFILE"] = _get_log_file_name()
XSH.aliases["xog"] = _xog
