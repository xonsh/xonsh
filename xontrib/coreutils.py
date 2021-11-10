"""Additional core utilities that are implemented in xonsh. The current list
includes:

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
from xonsh.xoreutils.cat import cat
from xonsh.xoreutils.echo import echo
from xonsh.xoreutils.pwd import pwd
from xonsh.xoreutils.tee import tee
from xonsh.xoreutils.tty import tty
from xonsh.xoreutils.yes import yes
import xonsh.session as xsh

__all__ = ()

xsh.XSH.aliases["cat"] = cat
xsh.XSH.aliases["echo"] = echo
xsh.XSH.aliases["pwd"] = pwd
xsh.XSH.aliases["tee"] = tee
xsh.XSH.aliases["tty"] = tty
xsh.XSH.aliases["yes"] = yes
