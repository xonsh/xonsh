"""Provides some Mac / Darwin based utility functions for xonsh."""
from ctypes import c_uint, byref, create_string_buffer

from xonsh.platform import LIBC


def sysctlbyname(name, return_str=True):
    """Gets a sysctl value by name. If return_str is true, this will return
    a string representation, else it will return the raw value.
    """
    # forked from https://gist.github.com/pudquick/581a71425439f2cf8f09
    size = c_uint(0)
    # Find out how big our buffer will be
    LIBC.sysctlbyname(name, None, byref(size), None, 0)
    # Make the buffer
    buf = create_string_buffer(size.value)
    # Re-run, but provide the buffer
    LIBC.sysctlbyname(name, buf, byref(size), None, 0)
    if return_str:
        return buf.value
    else:
        return buf.raw
