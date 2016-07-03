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
from xonsh.built_ins import subproc_captured_object
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
aliases['uncpushd'] = uncpushd

import builtins
import os
from xonsh.dirstack import DIRSTACK, pushd, popd

def unc_pushd( args, stdin=None):
    """Handle pushd when argument is a UNC path. (\\<server>\<share>...)
    If so, do like CMD.EXE pushd: create a temporary drive letter mapping, then pushd (via built-in) to that.
    For this to work nicely, user must already have access to the UNC path
    (e.g, via prior ```NET USE \\<server>\<share> /USER: ... /PASS:...```)

    Author considers this behavior intrusive, so the extension does not create an alias for this function automatically.
    If you want it, you must explicitly ask for it.
    """
    if ON_WINDOWS and args is not None and args[0] is not None and args[0][0] in (os.sep, os.altsep):
        share, relPath = os.path.splitdrive( args[0])
        if share[0] in (os.sep, os.altsep):
            tempDrive = 'z:'
            co = subproc_captured_object( ['net', 'use', tempDrive, share])
            if co.returncode != 0:
                return co.stdout, co.stderr, co.returncode
            else:

                return pushd( [os.path.join( tempDrive, relPath )], stdin)
    return pushd( args, stdin)

def unc_popd( args, stdin=None):
    """Handle popd from a temporary drive letter mapping established by `unc_pushd`
     If current working directory is one of the temporary mappings we created, and if it's not used further up in `DIRSTACK`,
     then unmap the drive letter (after returning from built-in popd with some other directory as PWD).
    """

    extraOutput = ''
    extraStderr = ''

    if not ON_WINDOWS:
        return popd(args, stdin)
    else:
        env = builtins.__xonsh_env__

        if env['PWD'] != os.getcwd():
            extraOutput += 'Warning: $PWD ({}) different from os.getcwd() ({})\n'.format( env['PWD'], os.getcwd()) + '  -- but proceeding anyway.\n'

        share, relPath = os.path.splitdrive( env['PWD'])
        tmpDrive = 'z:'

        pdResult = popd( args, stdin)       # pop first

        if share.lower() == tmpDrive:       # then delete the temp drive if needed
            co = subproc_captured_object(['net', 'use', tmpDrive, '/delete'])
            if co.returncode != 0:
                extraOutput += co.stdout
                extraStderr += co.stderr + '  -- but proceeding anyway\n'

        return ((pdResult[0] if pdResult[0] is not None else '') + extraOutput \
                , (pdResult[1] if pdResult[1] is not None else '') + extraStderr \
               , pdResult[2])

