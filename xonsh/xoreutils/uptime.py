"""
Provides a cross-platform way to figure out the system uptime.

Should work on damned near any operating system you can realistically expect
to be asked to write Python code for.
If this module is invoked as a stand-alone script, it will print the current
uptime in a human-readable format, or display an error message if it can't,
to standard output.

This file was forked from the uptime project: https://github.com/Cairnarvon/uptime
Copyright (c) 2012, Koen Crolla, All rights reserved.
"""
import os
import sys
import time
import ctypes
import struct

import xonsh.platform as xp
import xonsh.lazyimps as xlimps
import xonsh.lazyasd as xl


_BOOTTIME = None


def _uptime_osx():
    """Returns the uptime on mac / darwin."""
    global _BOOTTIME
    bt = xlimps.macutils.sysctlbyname(b"kern.boottime", return_str=False)
    if len(bt) == 4:
        bt = struct.unpack_from("@hh", bt)
    elif len(bt) == 8:
        bt = struct.unpack_from("@ii", bt)
    elif len(bt) == 16:
        bt = struct.unpack_from("@qq", bt)
    else:
        raise ValueError("length of boot time not understood: " + repr(bt))
    bt = bt[0] + bt[1] * 1e-6
    if bt == 0.0:
        return None
    _BOOTTIME = bt
    return time.time() - bt


def _uptime_linux():
    """Returns uptime in seconds or None, on Linux."""
    # With procfs
    try:
        with open("/proc/uptime", "r") as f:
            up = float(f.readline().split()[0])
        return up
    except (IOError, ValueError):
        pass
    buf = ctypes.create_string_buffer(128)  # 64 suffices on 32-bit, whatever.
    if xp.LIBC.sysinfo(buf) < 0:
        return None
    up = struct.unpack_from("@l", buf.raw)[0]
    if up < 0:
        up = None
    return up


def _boottime_linux():
    """A way to figure out the boot time directly on Linux."""
    global _BOOTTIME
    try:
        with open("/proc/stat", "r") as f:
            for line in f:
                if line.startswith("btime"):
                    _BOOTTIME = float(line.split()[1])
        return _BOOTTIME
    except (IOError, IndexError):
        return None


def _uptime_amiga():
    """Returns uptime in seconds or None, on AmigaOS."""
    global _BOOTTIME
    try:
        _BOOTTIME = os.stat("RAM:").st_ctime
        return time.time() - _BOOTTIME
    except (NameError, OSError):
        return None


def _uptime_beos():
    """Returns uptime in seconds on None, on BeOS/Haiku."""
    if not hasattr(xp.LIBC, "system_time"):
        return None
    xp.LIBC.system_time.restype = ctypes.c_int64
    return xp.LIBC.system_time() / 1000000.


def _uptime_bsd():
    """Returns uptime in seconds or None, on BSD (including OS X)."""
    global _BOOTTIME
    if not hasattr(xp.LIBC, "sysctlbyname"):
        # Not BSD.
        return None
    # Determine how much space we need for the response.
    sz = ctypes.c_uint(0)
    xp.LIBC.sysctlbyname("kern.boottime", None, ctypes.byref(sz), None, 0)
    if sz.value != struct.calcsize("@LL"):
        # Unexpected, let's give up.
        return None
    # For real now.
    buf = ctypes.create_string_buffer(sz.value)
    xp.LIBC.sysctlbyname("kern.boottime", buf, ctypes.byref(sz), None, 0)
    sec, usec = struct.unpack_from("@LL", buf.raw)
    # OS X disagrees what that second value is.
    if usec > 1000000:
        usec = 0.
    _BOOTTIME = sec + usec / 1000000.
    up = time.time() - _BOOTTIME
    if up < 0:
        up = None
    return up


def _uptime_minix():
    """Returns uptime in seconds or None, on MINIX."""
    try:
        with open("/proc/uptime", "r") as f:
            up = float(f.read())
        return up
    except (IOError, ValueError):
        return None


def _uptime_plan9():
    """Returns uptime in seconds or None, on Plan 9."""
    # Apparently Plan 9 only has Python 2.2, which I'm not prepared to
    # support. Maybe some Linuxes implement /dev/time, though, someone was
    # talking about it somewhere.
    try:
        # The time file holds one 32-bit number representing the sec-
        # onds since start of epoch and three 64-bit numbers, repre-
        # senting nanoseconds since start of epoch, clock ticks, and
        # clock frequency.
        #  -- cons(3)
        with open("/dev/time", "r") as f:
            s, ns, ct, cf = f.read().split()
        return float(ct) / float(cf)
    except (IOError, ValueError):
        return None


def _uptime_solaris():
    """Returns uptime in seconds or None, on Solaris."""
    global _BOOTTIME
    try:
        kstat = ctypes.CDLL("libkstat.so")
    except (AttributeError, OSError):
        return None

    # kstat doesn't have uptime, but it does have boot time.
    # Unfortunately, getting at it isn't perfectly straightforward.
    # First, let's pretend to be kstat.h

    # Constant
    KSTAT_STRLEN = 31  # According to every kstat.h I could find.

    # Data structures
    class anon_union(ctypes.Union):
        # The ``value'' union in kstat_named_t actually has a bunch more
        # members, but we're only using it for boot_time, so we only need
        # the padding and the one we're actually using.
        _fields_ = [("c", ctypes.c_char * 16), ("time", ctypes.c_int)]

    class kstat_named_t(ctypes.Structure):
        _fields_ = [
            ("name", ctypes.c_char * KSTAT_STRLEN),
            ("data_type", ctypes.c_char),
            ("value", anon_union),
        ]

    # Function signatures
    kstat.kstat_open.restype = ctypes.c_void_p
    kstat.kstat_lookup.restype = ctypes.c_void_p
    kstat.kstat_lookup.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
    ]
    kstat.kstat_read.restype = ctypes.c_int
    kstat.kstat_read.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    kstat.kstat_data_lookup.restype = ctypes.POINTER(kstat_named_t)
    kstat.kstat_data_lookup.argtypes = [ctypes.c_void_p, ctypes.c_char_p]

    # Now, let's do something useful.
    # Initialise kstat control structure.
    kc = kstat.kstat_open()
    if not kc:
        return None
    # We're looking for unix:0:system_misc:boot_time.
    ksp = kstat.kstat_lookup(kc, "unix", 0, "system_misc")
    if ksp and kstat.kstat_read(kc, ksp, None) != -1:
        data = kstat.kstat_data_lookup(ksp, "boot_time")
        if data:
            _BOOTTIME = data.contents.value.time
    # Clean-up.
    kstat.kstat_close(kc)
    if _BOOTTIME is not None:
        return time.time() - _BOOTTIME
    return None


def _uptime_syllable():
    """Returns uptime in seconds or None, on Syllable."""
    global _BOOTTIME
    try:
        _BOOTTIME = os.stat("/dev/pty/mst/pty0").st_mtime
        return time.time() - _BOOTTIME
    except (NameError, OSError):
        return None


def _uptime_windows():
    """
    Returns uptime in seconds or None, on Windows. Warning: may return
    incorrect answers after 49.7 days on versions older than Vista.
    """
    if hasattr(xp.LIBC, "GetTickCount64"):
        # Vista/Server 2008 or later.
        xp.LIBC.GetTickCount64.restype = ctypes.c_uint64
        return xp.LIBC.GetTickCount64() / 1000.
    if hasattr(xp.LIBC, "GetTickCount"):
        # WinCE and Win2k or later; gives wrong answers after 49.7 days.
        xp.LIBC.GetTickCount.restype = ctypes.c_uint32
        return xp.LIBC.GetTickCount() / 1000.
    return None


@xl.lazyobject
def _UPTIME_FUNCS():
    return {
        "amiga": _uptime_amiga,
        "aros12": _uptime_amiga,
        "beos5": _uptime_beos,
        "cygwin": _uptime_linux,
        "darwin": _uptime_osx,
        "haiku1": _uptime_beos,
        "linux": _uptime_linux,
        "linux-armv71": _uptime_linux,
        "linux2": _uptime_linux,
        "minix3": _uptime_minix,
        "sunos5": _uptime_solaris,
        "syllable": _uptime_syllable,
        "win32": _uptime_windows,
        "wince": _uptime_windows,
    }


def uptime():
    """Returns uptime in seconds if even remotely possible, or None if not."""
    if _BOOTTIME is not None:
        return time.time() - _BOOTTIME
    up = _UPTIME_FUNCS.get(sys.platform, _uptime_bsd)()
    if up is None:
        up = (
            _uptime_bsd()
            or _uptime_plan9()
            or _uptime_linux()
            or _uptime_windows()
            or _uptime_solaris()
            or _uptime_beos()
            or _uptime_amiga()
            or _uptime_syllable()
            or _uptime_osx()
        )
    return up


def boottime():
    """Returns boot time if remotely possible, or None if not."""
    global _BOOTTIME
    if _BOOTTIME is None:
        up = uptime()
        if up is None:
            return None
        _BOOTTIME = time.time() - up
    return _BOOTTIME
