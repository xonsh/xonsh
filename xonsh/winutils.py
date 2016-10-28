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
import sys
import subprocess
import msvcrt
import ctypes
from ctypes import c_ulong, c_char_p, c_int, c_void_p
from ctypes.wintypes import (HANDLE, BOOL, DWORD, HWND, HINSTANCE, HKEY, 
    LPDWORD, LPSTR, SHORT, LPWSTR, LPCWSTR)

from xonsh.lazyasd import lazyobject
from xonsh import lazyimps  # we aren't amagamated in this module.


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

    if not ShellExecuteEx(ctypes.byref(execute_info)):
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
ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004 # VT100 (Win 10)


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
    GetConsoleMode(hcon, ctypes.byref(mode))
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


class COORD(ctypes.Structure):
    _fields_ = [("X", SHORT),
                ("Y", SHORT)]        
 
@lazyobject
def ReadConsoleOutputCharacter():
    rcoc = ctypes.windll.kernel32.ReadConsoleOutputCharacterW
    rcoc.errcheck = check_zero
    rcoc.argtypes = (HANDLE,   # _In_  hConsoleOutput
                     LPCWSTR,  # _Out_ LPTSTR lpMode
                     DWORD,    # _In_  nLength
                     COORD,    # _In_  dwReadCoord,
                     LPDWORD)  # _Out_ lpNumberOfCharsRead
    rcoc.restype = BOOL
    return rcoc

    
def read_console_output_character(x=0, y=0, fd=1, buf=None, bufsize=1024):
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
    buf : ctypes.c_wchar_p, optional
        An existing buffer to (re-)use.
    bufsize : int, optional
        The maximum read size.
        
    Returns
    -------
    value : str
        Result of what was read, may be shorter than bufsize.
    """
    hcon = STDHANDLES[fd]
    if buf is None:
        buf = ctypes.c_wchar_p(" " * bufsize)
    coord = COORD(x, y)
    n = DWORD()
    ReadConsoleOutputCharacter(hcon, buf, bufsize, coord, ctypes.byref(n))
    return buf.value[:n.value]
 
 
def pread_console(fd, buffersize, offset, buf=None):
    """This is a console-based implementation of os.pread() for windows.
    that uses read_console_output_character().
    """
    cols, rows = os.get_terminal_size(fd=fd)
    x = offset % col
    y = offset // cols
    return read_console_output_character(x=x, y=y, fd=fd, buf=buf, 
                                         bufsize=buffersize)