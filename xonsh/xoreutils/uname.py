#!/usr/bin/env python

"""
Provides a cross-platform way to figure out the system uname.

This version of uname was written in Python for the xonsh project: http://xon.sh

Based on cat from GNU coreutils: http://www.gnu.org/software/coreutils/
"""

import platform
import sys

from xonsh.cli_utils import ArgParserAlias


def uname_fn(
    all=False,
    kernel_name=False,
    node_name=False,
    kernel_release=False,
    kernel_version=False,
    machine=False,
    processor=False,
    hardware_platform=False,
    operating_system=False,
):
    """This version of uname was written in Python for the xonsh project: https://xon.sh

    Based on uname from GNU coreutils: http://www.gnu.org/software/coreutils/


    Parameters
    ----------
    all : -a, --all
        print all information, in the following order, except omit -p and -i if unknown
    kernel_name : -s, --kernel-name
        print the kernel name
    node_name : -n, --nodename
        print the network node hostname
    kernel_release : -r, --kernel-release
        print the kernel release
    kernel_version : -v, --kernel-version
        print the kernel version
    machine : -m, --machine
        print the machine hardware name
    processor : -p, --processor
        print the processor type (non-portable)
    hardware_platform : -i, --hardware-platform
        print the hardware platform (non-portable)
    operating_system : -o, --operating-system
        print the operating system
    """

    info = platform.uname()

    def gen_lines():
        if all or node_name:
            yield info.node

        if all or kernel_release:
            yield info.release

        if all or kernel_version:
            yield info.version

        if all or machine:
            yield info.machine

        if all or processor:
            yield info.processor or "unknown"

        if all or hardware_platform:
            yield "unknown"

        if all or operating_system:
            yield sys.platform

    lines = list(gen_lines())
    if all or kernel_name or (not lines):
        lines.insert(0, info.system)
    line = " ".join(lines)

    return line


uname = ArgParserAlias(func=uname_fn, has_args=True, prog="uname")


def main(args=None):
    from xonsh.xoreutils.util import run_alias

    run_alias("uname", args)


if __name__ == "__main__":
    main()
