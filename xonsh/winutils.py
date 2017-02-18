"""
This file is based on the code from https://github.com/JustAMan/pyWinClobber/blob/master/win32elevate.py

Copyright (c) 2013 by JustAMan at GitHub

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""
import os
import sys
import ctypes
import subprocess
from ctypes import c_ulong, c_char_p, c_int, c_void_p, POINTER, byref
from ctypes.wintypes import (HANDLE, BOOL, DWORD, HWND, HINSTANCE, HKEY,
                             LPDWORD, SHORT, LPCWSTR, WORD, SMALL_RECT, LPCSTR)

from xonsh.lazyasd import lazyobject
from xonsh import lazyimps  # we aren't amagamated in this module.
from xonsh import platform


__all__ = ('sudo', )


@lazyobject
def CloseHandle():
    ch = ctypes.windll.kernel32.CloseHandle
    ch.argtypes = (HANDLE,)
    ch.restype = BOOL
    return ch


@lazyobject
def GetActiveWindow():
    gaw = ctypes.windll.user32.GetActiveWindow
    gaw.argtypes = ()
    gaw.restype = HANDLE
    return gaw


TOKEN_READ = 0x20008


class ShellExecuteInfo(ctypes.Structure):
    _fields_ = [
        ('cbSize', DWORD),
        ('fMask', c_ulong),
        ('hwnd', HWND),
        ('lpVerb', c_char_p),
        ('lpFile', c_char_p),
        ('lpParameters', c_char_p),
        ('lpDirectory', c_char_p),
        ('nShow', c_int),
        ('hInstApp', HINSTANCE),
        ('lpIDList', c_void_p),
        ('lpClass', c_char_p),
        ('hKeyClass', HKEY),
        ('dwHotKey', DWORD),
        ('hIcon', HANDLE),
        ('hProcess', HANDLE)
    ]

    def __init__(self, **kw):
        ctypes.Structure.__init__(self)
        self.cbSize = ctypes.sizeof(self)
        for field_name, field_value in kw.items():
            setattr(self, field_name, field_value)


@lazyobject
def ShellExecuteEx():
    see = ctypes.windll.Shell32.ShellExecuteExA
    PShellExecuteInfo = ctypes.POINTER(ShellExecuteInfo)
    see.argtypes = (PShellExecuteInfo, )
    see.restype = BOOL
    return see


@lazyobject
def WaitForSingleObject():
    wfso = ctypes.windll.kernel32.WaitForSingleObject
    wfso.argtypes = (HANDLE, DWORD)
    wfso.restype = DWORD
    return wfso


# SW_HIDE = 0
SW_SHOW = 5
SEE_MASK_NOCLOSEPROCESS = 0x00000040
SEE_MASK_NO_CONSOLE = 0x00008000
INFINITE = -1


def wait_and_close_handle(process_handle):
    """
    Waits till spawned process finishes and closes the handle for it

    Parameters
    ----------
    process_handle : HANDLE
        The Windows handle for the process
    """
    WaitForSingleObject(process_handle, INFINITE)
    CloseHandle(process_handle)


def sudo(executable, args=None):
    """
    This will re-run current Python script requesting to elevate administrative rights.

    Parameters
    ----------
    param executable : str
        The path/name of the executable
    args : list of str
        The arguments to be passed to the executable
    """
    if not args:
        args = []

    execute_info = ShellExecuteInfo(
        fMask=SEE_MASK_NOCLOSEPROCESS | SEE_MASK_NO_CONSOLE,
        hwnd=GetActiveWindow(),
        lpVerb=b'runas',
        lpFile=executable.encode('utf-8'),
        lpParameters=subprocess.list2cmdline(args).encode('utf-8'),
        lpDirectory=None,
        nShow=SW_SHOW
    )

    if not all(stream.isatty() for stream in (sys.stdin, sys.stdout, sys.stderr)):
        # TODO: Some streams were redirected, we need to manually work them
        raise NotImplementedError("Redirection is not supported")

    if not ShellExecuteEx(byref(execute_info)):
        raise ctypes.WinError()

    wait_and_close_handle(execute_info.hProcess)

#
# The following has been refactored from
# http://stackoverflow.com/a/37505496/2312428
#

# input flags
ENABLE_PROCESSED_INPUT = 0x0001
ENABLE_LINE_INPUT = 0x0002
ENABLE_ECHO_INPUT = 0x0004
ENABLE_WINDOW_INPUT = 0x0008
ENABLE_MOUSE_INPUT = 0x0010
ENABLE_INSERT_MODE = 0x0020
ENABLE_QUICK_EDIT_MODE = 0x0040

# output flags
ENABLE_PROCESSED_OUTPUT = 0x0001
ENABLE_WRAP_AT_EOL_OUTPUT = 0x0002
ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004  # VT100 (Win 10)


def check_zero(result, func, args):
    if not result:
        err = ctypes.get_last_error()
        if err:
            raise ctypes.WinError(err)
    return args


@lazyobject
def GetStdHandle():
    return lazyimps._winapi.GetStdHandle


@lazyobject
def STDHANDLES():
    """Tuple of the Windows handles for (stdin, stdout, stderr)."""
    hs = [lazyimps._winapi.STD_INPUT_HANDLE,
          lazyimps._winapi.STD_OUTPUT_HANDLE,
          lazyimps._winapi.STD_ERROR_HANDLE]
    hcons = []
    for h in hs:
        hcon = GetStdHandle(int(h))
        hcons.append(hcon)
    return tuple(hcons)


@lazyobject
def GetConsoleMode():
    gcm = ctypes.windll.kernel32.GetConsoleMode
    gcm.errcheck = check_zero
    gcm.argtypes = (HANDLE,   # _In_  hConsoleHandle
                    LPDWORD)  # _Out_ lpMode
    return gcm


def get_console_mode(fd=1):
    """Get the mode of the active console input, output, or error
    buffer. Note that if the process isn't attached to a
    console, this function raises an EBADF IOError.

    Parameters
    ----------
    fd : int
        Standard buffer file descriptor, 0 for stdin, 1 for stdout (default),
        and 2 for stderr
    """
    mode = DWORD()
    hcon = STDHANDLES[fd]
    GetConsoleMode(hcon, byref(mode))
    return mode.value


@lazyobject
def SetConsoleMode():
    scm = ctypes.windll.kernel32.SetConsoleMode
    scm.errcheck = check_zero
    scm.argtypes = (HANDLE,  # _In_  hConsoleHandle
                    DWORD)   # _Out_ lpMode
    return scm


def set_console_mode(mode, fd=1):
    """Set the mode of the active console input, output, or
    error buffer. Note that if the process isn't attached to a
    console, this function raises an EBADF IOError.

    Parameters
    ----------
    mode : int
        Mode flags to set on the handle.
    fd : int, optional
        Standard buffer file descriptor, 0 for stdin, 1 for stdout (default),
        and 2 for stderr
    """
    hcon = STDHANDLES[fd]
    SetConsoleMode(hcon, mode)


def enable_virtual_terminal_processing():
    """Enables virtual terminal processing on Windows.
    This inlcudes ANSI escape sequence interpretation.
    See http://stackoverflow.com/a/36760881/2312428
    """
    SetConsoleMode(GetStdHandle(-11), 7)


@lazyobject
def COORD():
    if platform.has_prompt_toolkit():
        # turns out that PTK has a separate ctype wrapper
        # for this struct and also wraps similar function calls
        # we need to use the same struct to prevent clashes.
        import prompt_toolkit.win32_types
        return prompt_toolkit.win32_types.COORD

    class _COORD(ctypes.Structure):
        """Struct from the winapi, representing coordinates in the console.

        Attributes
        ----------
        X : int
            Column position
        Y : int
            Row position
        """
        _fields_ = [("X", SHORT),
                    ("Y", SHORT)]

    return _COORD


@lazyobject
def ReadConsoleOutputCharacterA():
    rcoc = ctypes.windll.kernel32.ReadConsoleOutputCharacterA
    rcoc.errcheck = check_zero
    rcoc.argtypes = (HANDLE,   # _In_  hConsoleOutput
                     LPCSTR,   # _Out_ LPTSTR lpMode
                     DWORD,    # _In_  nLength
                     COORD,    # _In_  dwReadCoord,
                     LPDWORD)  # _Out_ lpNumberOfCharsRead
    rcoc.restype = BOOL
    return rcoc


@lazyobject
def ReadConsoleOutputCharacterW():
    rcoc = ctypes.windll.kernel32.ReadConsoleOutputCharacterW
    rcoc.errcheck = check_zero
    rcoc.argtypes = (HANDLE,   # _In_  hConsoleOutput
                     LPCWSTR,  # _Out_ LPTSTR lpMode
                     DWORD,    # _In_  nLength
                     COORD,    # _In_  dwReadCoord,
                     LPDWORD)  # _Out_ lpNumberOfCharsRead
    rcoc.restype = BOOL
    return rcoc


def read_console_output_character(x=0, y=0, fd=1, buf=None, bufsize=1024,
                                  raw=False):
    """Reads chracters from the console buffer.

    Parameters
    ----------
    x : int, optional
        Starting column.
    y : int, optional
        Starting row.
    fd : int, optional
        Standard buffer file descriptor, 0 for stdin, 1 for stdout (default),
        and 2 for stderr.
    buf : ctypes.c_wchar_p if raw else ctypes.c_wchar_p, optional
        An existing buffer to (re-)use.
    bufsize : int, optional
        The maximum read size.
    raw : bool, opional
        Whether to read in and return as bytes (True) or as a
        unicode string (False, default).

    Returns
    -------
    value : str
        Result of what was read, may be shorter than bufsize.
    """
    hcon = STDHANDLES[fd]
    if buf is None:
        if raw:
            buf = ctypes.c_char_p(b" " * bufsize)
        else:
            buf = ctypes.c_wchar_p(" " * bufsize)
    coord = COORD(x, y)
    n = DWORD()
    if raw:
        ReadConsoleOutputCharacterA(hcon, buf, bufsize, coord, byref(n))
    else:
        ReadConsoleOutputCharacterW(hcon, buf, bufsize, coord, byref(n))
    return buf.value[:n.value]


def pread_console(fd, buffersize, offset, buf=None):
    """This is a console-based implementation of os.pread() for windows.
    that uses read_console_output_character().
    """
    cols, rows = os.get_terminal_size(fd=fd)
    x = offset % cols
    y = offset // cols
    return read_console_output_character(x=x, y=y, fd=fd, buf=buf,
                                         bufsize=buffersize, raw=True)


#
# The following piece has been forked from colorama.win32
# Copyright Jonathan Hartley 2013. BSD 3-Clause license, see LICENSE file.
#

@lazyobject
def CONSOLE_SCREEN_BUFFER_INFO():
    if platform.has_prompt_toolkit():
        # turns out that PTK has a separate ctype wrapper
        # for this struct and also wraps kernel32.GetConsoleScreenBufferInfo
        # we need to use the same struct to prevent clashes.
        import prompt_toolkit.win32_types
        return prompt_toolkit.win32_types.CONSOLE_SCREEN_BUFFER_INFO

    # Otherwise we should wrap it ourselves
    COORD()  # force COORD to load

    class _CONSOLE_SCREEN_BUFFER_INFO(ctypes.Structure):
        """Struct from in wincon.h. See Windows API docs
        for more details.

        Attributes
        ----------
        dwSize : COORD
            Size of
        dwCursorPosition : COORD
            Current cursor location.
        wAttributes : WORD
            Flags for screen buffer.
        srWindow : SMALL_RECT
            Actual size of screen
        dwMaximumWindowSize : COORD
            Maximum window scrollback size.
        """
        _fields_ = [
            ("dwSize", COORD),
            ("dwCursorPosition", COORD),
            ("wAttributes", WORD),
            ("srWindow", SMALL_RECT),
            ("dwMaximumWindowSize", COORD),
            ]

    return _CONSOLE_SCREEN_BUFFER_INFO


@lazyobject
def GetConsoleScreenBufferInfo():
    """Returns the windows version of the get screen buffer."""
    gcsbi = ctypes.windll.kernel32.GetConsoleScreenBufferInfo
    gcsbi.errcheck = check_zero
    gcsbi.argtypes = (
        HANDLE,
        POINTER(CONSOLE_SCREEN_BUFFER_INFO),
        )
    gcsbi.restype = BOOL
    return gcsbi


def get_console_screen_buffer_info(fd=1):
    """Returns an screen buffer info object for the relevant stdbuf.

    Parameters
    ----------
    fd : int, optional
        Standard buffer file descriptor, 0 for stdin, 1 for stdout (default),
        and 2 for stderr.

    Returns
    -------
    csbi : CONSOLE_SCREEN_BUFFER_INFO
        Information about the console screen buffer.
    """
    hcon = STDHANDLES[fd]
    csbi = CONSOLE_SCREEN_BUFFER_INFO()
    GetConsoleScreenBufferInfo(hcon, byref(csbi))
    return csbi

#
# end colorama forked section
#


def get_cursor_position(fd=1):
    """Gets the current cursor position as an (x, y) tuple."""
    csbi = get_console_screen_buffer_info(fd=fd)
    coord = csbi.dwCursorPosition
    return (coord.X, coord.Y)


def get_cursor_offset(fd=1):
    """Gets the current cursor position as a total offset value."""
    csbi = get_console_screen_buffer_info(fd=fd)
    pos = csbi.dwCursorPosition
    size = csbi.dwSize
    return (pos.Y * size.X) + pos.X


def get_position_size(fd=1):
    """Gets the current cursor position and screen size tuple:
    (x, y, columns, lines).
    """
    info = get_console_screen_buffer_info(fd)
    return (info.dwCursorPosition.X, info.dwCursorPosition.Y,
            info.dwSize.X, info.dwSize.Y)


@lazyobject
def SetConsoleScreenBufferSize():
    """Set screen buffer dimensions."""
    scsbs = ctypes.windll.kernel32.SetConsoleScreenBufferSize
    scsbs.errcheck = check_zero
    scsbs.argtypes = (
        HANDLE,  # _In_ HANDLE hConsoleOutput
        COORD,   # _In_ COORD  dwSize
        )
    scsbs.restype = BOOL
    return scsbs


def set_console_screen_buffer_size(x, y, fd=1):
    """Sets the console size for a standard buffer.

    Parameters
    ----------
    x : int
        Number of columns.
    y : int
        Number of rows.
    fd : int, optional
        Standard buffer file descriptor, 0 for stdin, 1 for stdout (default),
        and 2 for stderr.
    """
    coord = COORD()
    coord.X = x
    coord.Y = y
    hcon = STDHANDLES[fd]
    rtn = SetConsoleScreenBufferSize(hcon, coord)
    return rtn


@lazyobject
def SetConsoleCursorPosition():
    """Set cursor position in console."""
    sccp = ctypes.windll.kernel32.SetConsoleCursorPosition
    sccp.errcheck = check_zero
    sccp.argtypes = (
        HANDLE,  # _In_ HANDLE hConsoleOutput
        COORD,   # _In_ COORD  dwCursorPosition
        )
    sccp.restype = BOOL
    return sccp


def set_console_cursor_position(x, y, fd=1):
    """Sets the console cursor position for a standard buffer.

    Parameters
    ----------
    x : int
        Number of columns.
    y : int
        Number of rows.
    fd : int, optional
        Standard buffer file descriptor, 0 for stdin, 1 for stdout (default),
        and 2 for stderr.
    """
    coord = COORD()
    coord.X = x
    coord.Y = y
    hcon = STDHANDLES[fd]
    rtn = SetConsoleCursorPosition(hcon, coord)
    return rtn
