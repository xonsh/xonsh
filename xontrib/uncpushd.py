"""Utilities for handling UNC (\\node\share\...) paths in PUSHD (on Windows)

    Current viersion of windows CMD.EXE enforce a check for working directory set to a UNC path
     and by default issue the error:
     >>>
CMD.EXE was started with the above path as the current directory.
UNC paths are not supported.  Defaulting to Windows directory.

    Apparently, MS is still worried about child processes created by such a shell which continue running after the shell closes.

    This module contains 2 ways to deal with it, because neither is a 100% complete solution.

    Background: see https://support.microsoft.com/en-us/kb/156276
"""

# (of all the brain-dead things to do! It doesn't fail, it warns and proceeds with a dangerous default, C:\windows.
# It would be much better to fail if they really mean it, and really can't fix the problem (which they don't describe, and may have been fixed long since....)
# And, if you must proceed , %WINDIR% is probably the worst fallback to use!
# Either (ordinary) user will fail reading or trying and failing to write a file, or (privileged) user may succeed in writing, possibly clobbering something important.
# -- there.  I feel much better.  To proceed...)

import argparse

from xonsh.lazyasd import LazyObject
from xonsh.built_ins import subproc_captured_object, subproc_uncaptured
from xonsh.platform import ON_WINDOWS

_uncpushd_choices = dict(enable=1, disable=0, show=None)

def _uncpushd_parser():
    parser = argparse.ArgumentParser(prog="uncpushd", description='Enable or disable CMD.EXE check for UNC path.')
    parser.add_argument('action', choices=_uncpushd_choices, default='show')
    return parser

uncpushd_parser = LazyObject(_uncpushd_parser, globals(), 'uncpushd_parser')

del _uncpushd_parser

def uncpushd(args=None, stdin=None):
    """Set, Clear or display current value for DisableUNCCheck in registry, controls
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
        co = subproc_captured_object(
            ['reg', 'query', '"hkcu\software\microsoft\command processor"', '-v', 'DisableUNCCheck'])
        if co.returncode == 0:
            return 'enabled\n' if co.stdout[-3:-2] == '1' else 'disabled\n'\
                , None, 0-int(co.stdout[-3:-2])
        else:
            return 'disabled\n', None, 0
    else:                               # set to 1 or 0
        co = subproc_captured_object(
            ['reg', 'add', '"hkcu\software\microsoft\command processor"', '-v', 'DisableUNCCheck', '-t', 'REG_DWORD',
             '-d', '1' if _uncpushd_choices[args.action] else '0', '-f'])
        return None if co.returncode == 0 else co.stdout, None if co.returncode == 0 else co.stderr, co.returncode
    pass

import builtins
import os
from xonsh.dirstack import pushd, popd, DIRSTACK
import subprocess

def do_subproc( args, msg=''):
    """Because `subproc_captured_object` fails with error `Workstation Service not started` on a `NET USE dd: \\localhost\share`..."""
    co = subprocess.run(args, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if co.returncode != 0:
        print('subproc returncode {}'.format(co.returncode, msg))
        print(' '.join(co.args))
        print(co.stdout)
        print(co.stderr)
        ##assert co.returncode==0, 'NET SHARE failed'
    return co.stdout, co.stderr, co.returncode

_unc_tempDrives = {}  # drivePart: tempDriveLetter for temp drive letters we create

def unc_pushd( args, stdin=None):
    """Handle pushd when argument is a UNC path. (\\<server>\<share>...)
    If so, do like CMD.EXE pushd: create a temporary drive letter mapping, then pushd (via built-in) to that.
    For this to work nicely, user must already have access to the UNC path
    (e.g, via prior ```NET USE \\<server>\<share> /USER: ... /PASS:...```)

    Author considers this behavior intrusive, so the extension does not create an alias for this function automatically.
    If you want it, you must explicitly ask for it, e.g ```aliases['pushd']=unc_pushd; aliases['popd']=unc_popd```.
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
                    co = do_subproc( ['net', 'use', dpath, share], msg='unc_pushd')
                    if co[2] != 0:
                        do_subproc( ['whoami', '/all'])
                        return co
                    else:
                        _unc_tempDrives[dpath] = share
                        return pushd( [os.path.join( dpath, relPath )], stdin)

def unc_popd( args, stdin=None):
    """Handle popd from a temporary drive letter mapping established by `unc_pushd`
     If current working directory is one of the temporary mappings we created, and if it's not used further up in `DIRSTACK`,
     then unmap the drive letter (after returning from built-in popd with some other directory as PWD).
    """

    if not ON_WINDOWS:
        return popd(args, stdin)
    else:
        stdout = ''
        stderr = ''

        env = builtins.__xonsh_env__
        share, relPath = os.path.splitdrive( env['PWD'])

        pdResult = popd( args, stdin)       # pop first

        if share in _unc_tempDrives:
            dpath = share
            for p in DIRSTACK:
                if share == os.path.splitdrive(p)[0]:
                    dpath = None
            if dpath is not None:
                _unc_tempDrives.pop(dpath)
                co = subproc_captured_object(['net', 'use', dpath, '/delete'])
                if co.returncode != 0:
                    stdout += co.stdout
                    stderr += co.stderr

        return ((pdResult[0] if pdResult[0] is not None else '') + stdout \
                , (pdResult[1] if pdResult[1] is not None else '') + stderr \
               , pdResult[2])



#todo: cleanup is not removing uses, should loop through _unc_tempDrives (or we need unc_dirstack -c
#todo: why doesn't popd clean up??