import io
import sys
import typing as tp

import xonsh.lazyimps as xli
import xonsh.tools as xt


def safe_open(fname, mode, buffering=-1):
    """Safely attempts to open a file in for xonsh subprocs."""
    # file descriptors
    try:
        return open(fname, mode, buffering=buffering)
    except PermissionError:
        raise xt.XonshError(f"xonsh: {fname}: permission denied")
    except FileNotFoundError:
        raise xt.XonshError(f"xonsh: {fname}: no such file or directory")
    except Exception:
        raise xt.XonshError(f"xonsh: {fname}: unable to open file")


def safe_close(x):
    """Safely attempts to close an object."""
    if not isinstance(x, io.IOBase):
        return
    if x.closed:
        return
    try:
        x.close()
    except Exception:
        pass


def _get_winsize(stream):
    if stream.isatty():
        return xli.fcntl.ioctl(stream.fileno(), xli.termios.TIOCGWINSZ, b"0000")


def _safe_pipe_properties(
    fd, _type: "tp.Literal['in', 'out', 'err']" = "out", use_tty=False
) -> None:
    """Makes sure that a pipe file descriptor properties are sane."""
    if not use_tty:
        return
    # due to some weird, long standing issue in Python, PTYs come out
    # replacing newline \n with \r\n. This causes issues for raw unix
    # protocols, like git and ssh, which expect unix line endings.
    # see https://mail.python.org/pipermail/python-list/2013-June/650460.html
    # for more details and the following solution.
    props = xli.termios.tcgetattr(fd)
    props[1] = props[1] & (~xli.termios.ONLCR) | xli.termios.ONLRET
    xli.termios.tcsetattr(fd, xli.termios.TCSANOW, props)
    # newly created PTYs have a stardard size (24x80), set size to the same size
    # than the current terminal
    winsize = None

    stream = {"in": sys.stdin, "err": sys.stderr, "out": sys.stdout}.get(_type)
    if stream:
        winsize = _get_winsize(stream)
    if winsize is not None:
        xli.fcntl.ioctl(fd, xli.termios.TIOCSWINSZ, winsize)
