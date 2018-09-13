"""A pwd implementation for xonsh."""
import os


def pwd(args, stdin, stdout, stderr):
    """A pwd implementation"""
    e = __xonsh__.env["PWD"]
    if "-h" in args or "--help" in args:
        print(PWD_HELP, file=stdout)
        return 0
    if "-P" in args:
        e = os.path.realpath(e)
    print(e, file=stdout)
    return 0


PWD_HELP = """Usage: pwd [OPTION]...
Print the full filename of the current working directory.

  -P, --physical   avoid all symlinks
      --help       display this help and exit

This version of pwd was written in Python for the xonsh project: http://xon.sh
Based on pwd from GNU coreutils: http://www.gnu.org/software/coreutils/"""


# Not Implemented
#   -L, --logical    use PWD from environment, even if it contains symlinks
