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

import ctypes
from ctypes.wintypes import HANDLE, BOOL, DWORD, HWND, HINSTANCE, HKEY
from ctypes import c_ulong, c_char_p, c_int, c_void_p

P_HANDLE = ctypes.POINTER(HANDLE)
P_WORD = ctypes.POINTER(DWORD)

CloseHandle = ctypes.windll.kernel32.CloseHandle
CloseHandle.argtypes = (HANDLE, )
CloseHandle.restype = BOOL

GetActiveWindow = ctypes.windll.user32.GetActiveWindow
GetActiveWindow.argtypes = ()
GetActiveWindow.restype = HANDLE

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

PShellExecuteInfo = ctypes.POINTER(ShellExecuteInfo)

ShellExecuteEx = ctypes.windll.Shell32.ShellExecuteExA
ShellExecuteEx.argtypes = (PShellExecuteInfo, )
ShellExecuteEx.restype = BOOL

WaitForSingleObject = ctypes.windll.kernel32.WaitForSingleObject
WaitForSingleObject.argtypes = (HANDLE, DWORD)
WaitForSingleObject.restype = DWORD

# SW_HIDE = 0
SW_SHOW = 5
SEE_MASK_NOCLOSEPROCESS = 0x00000040
SEE_MASK_NO_CONSOLE = 0x00008000
INFINITE = -1


def wait_and_close_handle(process_handle):
    """
    Waits till spawned process finishes and closes the handle for it

    :param process_handle: The Windows handle for the process
    :type process_handle: HANDLE
    """
    WaitForSingleObject(process_handle, INFINITE)
    CloseHandle(process_handle)


def sudo(executable, args=None):
    """
    This will re-run current Python script requesting to elevate administrative rights.

    :param executable: The path/name of the executable
    :type executable: str
    :param args: The arguments to be passed to the executable
    :type args: list
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


__all__ = ('sudo', )
