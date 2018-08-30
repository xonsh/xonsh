"""An implementation of yes for xonsh."""


def yes(args, stdin, stdout, stderr):
    """A yes command."""
    if "--help" in args:
        print(YES_HELP, file=stdout)
        return 0

    to_print = ["y"] if len(args) == 0 else [str(i) for i in args]

    while True:
        print(*to_print, file=stdout)

    return 0


YES_HELP = """Usage: yes [STRING]...
  or:  yes OPTION
Repeatedly output a line with all specified STRING(s), or 'y'.

      --help     display this help and exit

This version of yes was written in Python for the xonsh project: http://xon.sh
Based on yes from GNU coreutils: http://www.gnu.org/software/coreutils/"""
