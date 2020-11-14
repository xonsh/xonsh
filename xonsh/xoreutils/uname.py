#!/usr/bin/env python

"""
Provides a cross-platform way to figure out the system uname.

This version of uname was written in Python for the xonsh project: http://xon.sh

Based on cat from GNU coreutils: http://www.gnu.org/software/coreutils/
"""
import platform
import sys
import os

from xonsh.xoreutils.util import arg_handler
from xonsh import __version__


def uname(args, stdin, stdout, stderr):
    """
    Print certain system information.

    Parameters
    ----------
    args : list or None
           Arguments like -a
    stdin : sys.stdin
            The standard input
    stdout : sys.stdout
           The standard output
    stderr : sys.stderr
           The standard error
    """
    if stdout is None:
        stdout = sys.stdout

    opts = _uname_parse_args(args)

    if opts is None:
        opts = {
            "kernel_name": False,
            "nodename": False,
            "kernel_release": False,
            "kernel_version": False,
            "machine": False,
            "processor": False,
            "hardware_platform": False,
            "operating_system": False,
            "version": False,
            "help": False,
        }

    # control
    everything_is_false = True
    for key, value in opts.items():
        if key not in [
            "all",
            "kernel_name",
            "nodename",
            "kernel_release",
            "kernel_version",
            "machine",
            "processor",
            "hardware_platform",
            "operating_system",
            "version",
            "help",
        ]:
            stdout.write(f"{__name__}: unrecognized option '{key}'{os.linesep}")
            stdout.write(f"Try 'uname --help' for more information.{os.linesep}")
            stdout.flush()
            opts["help"] = True
        if value:
            everything_is_false = False

    if opts["help"]:
        stdout.write(UNAME_HELP)
        stdout.write(f"{os.linesep}")
        stdout.flush()
        return 0

    if everything_is_false:
        opts["kernel_name"] = True

    if opts["version"]:
        stdout.write(f"uname (xonsh) {__version__}{os.linesep}")
        stdout.flush()
        return 0

    line = []
    if "all" in opts and opts["all"]:
        opts["kernel_name"] = True
        opts["nodename"] = True
        opts["kernel_release"] = True
        opts["kernel_version"] = True
        opts["machine"] = True
        opts["processor"] = False
        opts["hardware_platform"] = False
        opts["operating_system"] = True

    if opts["kernel_name"]:
        line.append(platform.uname().system)

    if opts["nodename"]:
        line.append(platform.uname().node)

    if opts["kernel_release"]:
        line.append(platform.uname().release)

    if opts["kernel_version"]:
        line.append(platform.uname().version)

    if opts["machine"]:
        line.append(platform.uname().machine)

    if opts["processor"]:
        if len(platform.uname().processor) <= 0:
            line.append("unknown")
        else:
            line.append(platform.uname().processor)

    if opts["hardware_platform"]:
        line.append("unknown")

    if opts["operating_system"]:
        line.append(sys.platform)

    if line:
        stdout.write("{0}{1}".format(" ".join(line), os.linesep))
        stdout.flush()


def _uname_parse_args(args):
    """
    Internal function for parse args

    Parameters
    ----------
    args : list
           Arguments like -a

    Returns
    -------
    list or None
        A clean arguments list.
    """
    out = {
        "all": False,
        "kernel_name": False,
        "nodename": False,
        "kernel_release": False,
        "kernel_version": False,
        "machine": False,
        "processor": False,
        "hardware_platform": False,
        "operating_system": False,
        "version": False,
        "help": False,
    }

    arg_handler(args, out, "-a", "all", True, "--all")
    arg_handler(args, out, "-s", "kernel_name", True, "--kernel-name")
    arg_handler(args, out, "-n", "nodename", True, "--nodename")
    arg_handler(args, out, "-r", "kernel_release", True, "--kernel-release")
    arg_handler(args, out, "-v", "kernel_version", True, "--kernel-version")
    arg_handler(args, out, "-m", "machine", True, "--machine")
    arg_handler(args, out, "-p", "processor", True, "--processor")
    arg_handler(args, out, "-i", "hardware_platform", True, "--hardware-platform")
    arg_handler(args, out, "-o", "operating_system", True, "--operating-system")
    arg_handler(args, out, None, "version", True, "--version")
    arg_handler(args, out, None, "help", True, "--help")

    return out


UNAME_HELP = """This version of cat was written in Python for the xonsh project: http://xon.sh
Based on cat from GNU coreutils: http://www.gnu.org/software/coreutils/

Usage: uname [OPTION]...
Print certain system information.  With no OPTION, same as -s.

  -a, --all                print all information, in the following order,
                             except omit -p and -i if unknown:
  -s, --kernel-name        print the kernel name
  -n, --nodename           print the network node hostname
  -r, --kernel-release     print the kernel release
  -v, --kernel-version     print the kernel version
  -m, --machine            print the machine hardware name
  -p, --processor          print the processor type (non-portable)
  -i, --hardware-platform  print the hardware platform (non-portable)
  -o, --operating-system   print the operating system
      --help     display this help and exit
      --version  output version information and exit"""


def uname_main(args=None):
    """
    This version of uname was written in Python for the xonsh project: http://xon.sh
    Based on cat from GNU coreutils: http://www.gnu.org/software/coreutils/

    Parameters
    ----------
    args : list
           Arguments like -a
    """
    import sys
    from xonsh.main import setup

    setup()
    args = sys.argv[1:] if args is None else args
    uname(args, sys.stdin, sys.stdout, sys.stderr)


if __name__ == "__main__":
    uname_main()
