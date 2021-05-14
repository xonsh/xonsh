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
from xonsh.built_ins import XSH

__all__ = ()

XSH.aliases["cat"] = cat
XSH.aliases["echo"] = echo
XSH.aliases["pwd"] = pwd
XSH.aliases["tee"] = tee
XSH.aliases["tty"] = tty
XSH.aliases["yes"] = yes
