"""Utilities for handling UNC (\\node\share\...) paths in PUSHD (on Windows)

    Current viersion of windows CMD.EXE enforce a check for working directory set to a UNC path
     and by default issue the error:
     >>>
CMD.EXE was started with the above path as the current directory.
UNC paths are not supported.  Defaulting to Windows directory.

    Apparently, MS is still worried about child processes created by such a shell which continue running after the shell closes.

    This module contains 2 ways to deal with it, because neither is perfect.

    Background: see https://support.microsoft.com/en-us/kb/156276
"""

# (of all the brain-dead things to do! CMD.EXE doesn't fail, it warns and proceeds with a dangerous default, C:\windows.
# It would be much better to fail if they really mean it, and really can't fix the problem (which they don't describe, and may have been fixed long since....)
# And, if you must proceed , %WINDIR% is probably the worst fallback to use!
# Either (ordinary) user will fail reading or trying and failing to write a file, or (privileged) user may succeed in writing, possibly clobbering something important.
# -- there.  I feel much better now.  To proceed...)

import argparse
import builtins
import os
import subprocess
import winreg

from xonsh.lazyasd import lazyobject
from xonsh.platform import ON_WINDOWS
from xonsh.dirstack import pushd, popd, DIRSTACK

_uncpushd_choices = dict(enable=1, disable=0, show=None)

@lazyobject
def uncpushd_parser():
    parser = argparse.ArgumentParser(prog="uncpushd", description='Enable or disable CMD.EXE check for UNC path.')
    parser.add_argument('action', choices=_uncpushd_choices, default='show')
    return parser

def uncpushd(args=None, stdin=None):
    """Fix alternative 1: configure CMD.EXE to bypass the chech for UNC path.
	Set, Clear or display current value for DisableUNCCheck in registry, which controls
    whether CMD.EXE complains when working directory set to a UNC path.

    In new windows install, value is not set, so if we cannot query the current value, assume check is enabled
    (meaning CMD.EXE complains).

    Does nothing on non-Windows platforms.
    """

    if not ON_WINDOWS:
        return None, None, 0

    try:
        args = uncpushd_parser.parse_args(args)
    except SystemExit:
        return None, None

    if _uncpushd_choices[args.action] is None:             # show current value
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'software\microsoft\command processor')
            wval, wtype = winreg.QueryValueEx(key, 'DisableUNCCheck')
            winreg.CloseKey(key)
            if wtype == winreg.REG_DWORD and wval:
                return 'enabled', None, 0
        except OSError as e:
            pass
        return 'disabled', None, 0
    else:                               # set to 1 or 0
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'software\microsoft\command processor')
            winreg.SetValueEx( key, 'DisableUNCCheck', 0, winreg.REG_DWORD, 1 if _uncpushd_choices[args.action] else 0)
            winreg.CloseKey( key)
            return None, None, 0
        except OSError as e:
            return None, str(OSError), 1

def _do_subprocess( *args)->tuple:
    """
    Invoke `args`, outputs and return code
    Args:
        *args: sequence of strings, as for `subprocess.check_output`

    Returns:
        tuple of:
            stdout:str      - stdout+stderr from subprocess (if it worked), or None
            stderr:str      - stdout+stderr from subprocess (if it didn't), or None
            return_code:int - return code from subprocess
    """
    try:
        return  subprocess.check_output( *args, universal_newlines=True, stderr=subprocess.STDOUT) \
                , None \
                , 0
    except subprocess.CalledProcessError as e:
        return  None, e.output, e.returncode


_unc_tempDrives = {}  # drivePart: tempDriveLetter for temp drive letters we create

def unc_pushd( args, stdin=None):
    """Fix 2: Handle pushd when argument is a UNC path (\\<server>\<share>...) the same way CMD.EXE does.
    Create a temporary drive letter mapping, then pushd (via built-in) to that path.
    For this to work nicely, user must already have access to the UNC path
    (e.g, via prior ```NET USE \\<server>\<share> /USER: ... /PASS:...```)

    """
    if not ON_WINDOWS or args is None or args[0] is None or args[0][0] not in (os.sep, os.altsep):
        return pushd(args, stdin)
    else:
        share, relPath = os.path.splitdrive( args[0])
        if share[0] not in (os.sep, os.altsep):
            return pushd(args, stdin)
        else:                                                # path begins \\ or //...
            for dord in range(ord('z'), ord('a'), -1):
                dpath = chr(dord) + ':'
                if not os.path.isdir(dpath):                # find unused drive letter starting from z:
                    co = _do_subprocess(['net', 'use', dpath, share])
                    if co[2] != 0:
                        return co
                    else:
                        _unc_tempDrives[dpath] = share
                        return pushd( [os.path.join( dpath, relPath )], stdin)
def _coalesce( a1, a2):
    """ return a1 + a2, treating None as ''.  But return None if both a1 and a2 are None."""
    retVal = ''
    if a1 is not None:
        retVal = a1
    if a2 is not None:
        retVal += a2

    return retVal if retVal != '' else None

def unc_popd( args, stdin=None):
    """Handle popd from a temporary drive letter mapping established by `unc_pushd`
     If current working directory is one of the temporary mappings we created, and if it's not used in the remaining directory stack (which is [PWD] + `DIRSTACK`),
     then unmap the drive letter (after returning from built-in popd with some other directory as PWD).

     Don't muck with popd semantics.  Return code is whatever `dirstack.popd` provides even if unmap operation fails.
     And *last* line of stdout and stderr are whatever came from popd.
    """
    if not ON_WINDOWS:
        return popd(args, stdin)
    else:
        co = None, None, 0
        env = builtins.__xonsh_env__
        drive, relPath = os.path.splitdrive( env['PWD'].casefold())     ## os.getcwd() uppercases drive letters on Windows?!

        pdResult = popd( args, stdin)       # pop first

        if drive in _unc_tempDrives:
            for p in [os.getcwd().casefold()] + DIRSTACK:               #hard_won: what dirs command shows is wd + contents of DIRSTACK
                if drive == os.path.splitdrive(p)[0].casefold():
                    drive = None
            if drive is not None:
                _unc_tempDrives.pop(drive)
                co = _do_subprocess(['net', 'use', drive, '/delete'])

        return _coalesce( pdResult[0], co[0])\
            , _coalesce( pdResult[1], co[1])\
            , pdResult[2]
