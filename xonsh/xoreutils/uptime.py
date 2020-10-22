#!/usr/bin/env python
"""
Provides a cross-platform way to figure out the system uptime.

Should work on damned near any operating system you can realistically expect
to be asked to write Python code for.
If this module is invoked as a stand-alone script, it will print the current
uptime in a human-readable format, or display an error message if it can't,
to standard output.

File forked from: https://github.com/Cairnarvon/uptime
"""
import sys
import time

try:
    from locale import *

    setlocale(LC_ALL, "")
except ImportError:
    pass

try:
    # So many broken ctypeses out there.
    import ctypes
except ImportError:
    ctypes = None

try:
    from struct import *
except ImportError:
    pass

try:
    from os import *
except ImportError:
    pass

try:
    from datetime import datetime
except ImportError:
    datetime = None

# RISC OS only but actually unsupported by xonsh
# try:
#     import swi
# except ImportError:
#     pass

try:
    from _posix import _uptime_posix, _uptime_osx
except ImportError:
    _uptime_posix = lambda: None
    _uptime_osx = lambda: None

__all__ = ["uptime", "boottime"]

__boottime = None


def _uptime_linux():
    """Returns uptime in seconds or None, on Linux."""
    # With procfs
    try:
        f = open("/proc/uptime", "r")
        up = float(f.readline().split()[0])
        f.close()
        return up
    except (IOError, ValueError):
        pass

    # Without procfs (really?)
    try:
        libc = ctypes.CDLL("libc.so")
    except AttributeError:
        return None
    except OSError:
        # Debian and derivatives do the wrong thing because /usr/lib/libc.so
        # is a GNU ld script rather than an ELF object. To get around this, we
        # have to be more specific.
        # We don't want to use ctypes.util.find_library because that creates a
        # new process on Linux. We also don't want to try too hard because at
        # this point we're already pretty sure this isn't Linux.
        try:
            libc = ctypes.CDLL("libc.so.6")
        except OSError:
            return None

    if not hasattr(libc, "sysinfo"):
        # Not Linux.
        return None

    buf = ctypes.create_string_buffer(128)  # 64 suffices on 32-bit, whatever.
    if libc.sysinfo(buf) < 0:
        return None

    up = unpack_from("@l", buf.raw)[0]
    if up < 0:
        up = None
    return up


def _boottime_linux():
    """A way to figure out the boot time directly on Linux."""
    global __boottime
    try:
        f = open("/proc/stat", "r")
        for line in f:
            if line.startswith("btime"):
                __boottime = int(line.split()[1])

        if datetime is None:
            raise NotImplementedError("datetime module required.")

        return datetime.fromtimestamp(__boottime)
    except (IOError, IndexError):
        return None


def _uptime_amiga():
    """Returns uptime in seconds or None, on AmigaOS."""
    global __boottime
    try:
        __boottime = stat("RAM:").st_ctime
        return time.time() - __boottime
    except (NameError, OSError):
        return None


def _uptime_beos():
    """Returns uptime in seconds on None, on BeOS/Haiku."""
    try:
        libroot = ctypes.CDLL("libroot.so")
    except (AttributeError, OSError):
        return None

    if not hasattr(libroot, "system_time"):
        return None

    libroot.system_time.restype = ctypes.c_int64
    return libroot.system_time() / 1000000.0


def _uptime_bsd():
    """Returns uptime in seconds or None, on BSD (including OS X)."""
    global __boottime
    try:
        libc = ctypes.CDLL("libc.so")
    except AttributeError:
        return None
    except OSError:
        # OS X; can't use ctypes.util.find_library because that creates
        # a new process on Linux, which is undesirable.
        try:
            libc = ctypes.CDLL("libc.dylib")
        except OSError:
            return None

    if not hasattr(libc, "sysctlbyname"):
        # Not BSD.
        return None

    # Determine how much space we need for the response.
    sz = ctypes.c_uint(0)
    libc.sysctlbyname("kern.boottime", None, ctypes.byref(sz), None, 0)
    if sz.value != calcsize("@LL"):
        # Unexpected, let's give up.
        return None

    # For real now.
    buf = ctypes.create_string_buffer(sz.value)
    libc.sysctlbyname("kern.boottime", buf, ctypes.byref(sz), None, 0)
    sec, usec = unpack("@LL", buf.raw)

    # OS X disagrees what that second value is.
    if usec > 1000000:
        usec = 0.0

    __boottime = sec + usec / 1000000.0
    up = time.time() - __boottime
    if up < 0:
        up = None
    return up


def _uptime_minix():
    """Returns uptime in seconds or None, on MINIX."""
    try:
        f = open("/proc/uptime", "r")
        up = float(f.read())
        f.close()
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
        f = open("/dev/time", "r")
        s, ns, ct, cf = f.read().split()
        f.close()
        return float(ct) / float(cf)
    except (IOError, ValueError):
        return None


# RiscOS is unsupported by oxnsh
# def _uptime_riscos():
#     """Returns uptime in seconds or None, on RISC OS."""
#     try:
#         up = swi.swi("OS_ReadMonotonicTime", ";i")
#         if up < 0:
#             # Overflows after about eight months on 32-bit.
#             return None
#         return up / 100.0
#     except NameError:
#         return None


def _uptime_solaris():
    """Returns uptime in seconds or None, on Solaris."""
    global __boottime
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
            __boottime = data.contents.value.time

    # Clean-up.
    kstat.kstat_close(kc)

    if __boottime is not None:
        return time.time() - __boottime

    return None


def _uptime_syllable():
    """Returns uptime in seconds or None, on Syllable."""
    global __boottime
    try:
        __boottime = stat("/dev/pty/mst/pty0").st_mtime
        return time.time() - __boottime
    except (NameError, OSError):
        return None


def _uptime_windows():
    """
    Returns uptime in seconds or None, on Windows. Warning: may return
    incorrect answers after 49.7 days on versions older than Vista.
    """
    if hasattr(ctypes, "windll") and hasattr(ctypes.windll, "kernel32"):
        lib = ctypes.windll.kernel32
    else:
        try:
            # Windows CE uses the cdecl calling convention.
            lib = ctypes.CDLL("coredll.lib")
        except (AttributeError, OSError):
            return None

    if hasattr(lib, "GetTickCount64"):
        # Vista/Server 2008 or later.
        lib.GetTickCount64.restype = ctypes.c_uint64
        return lib.GetTickCount64() / 1000.0
    if hasattr(lib, "GetTickCount"):
        # WinCE and Win2k or later; gives wrong answers after 49.7 days.
        lib.GetTickCount.restype = ctypes.c_uint32
        return lib.GetTickCount() / 1000.0
    return None


def uptime():
    """Returns uptime in seconds if even remotely possible, or None if not."""
    global __boottime

    if __boottime is not None:
        return time.time() - __boottime

    return (
            {
                "amiga": _uptime_amiga,
                "aros12": _uptime_amiga,
                "beos5": _uptime_beos,
                "cygwin": _uptime_linux,
                "darwin": _uptime_osx,
                "haiku": _uptime_beos,
                "haiku1": _uptime_beos,
                "linux": _uptime_linux,
                "linux-armv71": _uptime_linux,
                "linux2": _uptime_linux,
                # "mac": _uptime_mac,
                "minix3": _uptime_minix,
                # "riscos": _uptime_riscos,
                "sunos5": _uptime_solaris,
                "syllable": _uptime_syllable,
                "win32": _uptime_windows,
                "wince": _uptime_windows,
            }.get(sys.platform, _uptime_bsd)()
            or _uptime_bsd()
            or _uptime_plan9()
            or _uptime_linux()
            or _uptime_windows()
            or _uptime_solaris()
            or _uptime_beos()
            or _uptime_amiga()
            # or _uptime_riscos()
            or _uptime_posix()
            or _uptime_syllable()
            # or _uptime_mac()
            or _uptime_osx()
    )


def boottime():
    """Returns boot time if remotely possible, or None if not."""
    global __boottime, up

    if __boottime is None:
        up = uptime()
        if up is None:
            return None
    if __boottime is None:
        _boottime_linux()

    if datetime is None:
        raise RuntimeError("datetime module required.")

    return __boottime or time.time() - up


if __name__ == "__main__":
    up = uptime()

    if up is None:
        sys.stderr.write("Unable to determine uptime. Patches welcome.\n")
        sys.exit(1)

    if "-b" not in sys.argv:
        parts = []

        days, up = up // 86400, up % 86400
        if days:
            parts.append("%d day%s" % (days, "s" if days != 1 else ""))

        hours, up = up // 3600, up % 3600
        if hours:
            parts.append("%d hour%s" % (hours, "s" if hours != 1 else ""))

        minutes, up = up // 60, up % 60
        if minutes:
            parts.append("%d minute%s" % (minutes, "s" if minutes != 1 else ""))

        if up or not parts:
            parts.append("%.2f seconds" % up)

        sys.stdout.write("Uptime: %s.\n" % ", ".join(parts))
    else:
        sys.stdout.write(boottime().strftime("Booted: %c.\n"))
