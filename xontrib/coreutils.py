"""Additional core utilities that are implemented in xonsh.

The current list includes:

* cat
* echo
* pwd
* tee
* tty
* yes

In many cases, these may have a lower performance overhead than the
posix command line utility with the same name. This is because these
tools avoid the need for a full subprocess call. Additionally, these
tools are cross-platform.
"""
from xonsh.built_ins import XonshSession
from xonsh.platform import ON_POSIX
from xonsh.xoreutils.cat import cat
from xonsh.xoreutils.echo import echo
from xonsh.xoreutils.pwd import pwd
from xonsh.xoreutils.tee import tee
from xonsh.xoreutils.tty import tty
from xonsh.xoreutils.umask import umask
from xonsh.xoreutils.uname import uname
from xonsh.xoreutils.uptime import uptime
from xonsh.xoreutils.yes import yes


def _load_xontrib_(xsh: XonshSession, **_):
    xsh.aliases.register(cat)
    xsh.aliases.register(echo)
    xsh.aliases.register(pwd)
    xsh.aliases.register(tee)
    xsh.aliases.register(tty)
    xsh.aliases.register(uname)
    xsh.aliases.register(uptime)
    xsh.aliases.register(umask)
    xsh.aliases.register(yes)
    if ON_POSIX:
        from xonsh.xoreutils.ulimit import ulimit

        xsh.aliases["ulimit"] = ulimit
