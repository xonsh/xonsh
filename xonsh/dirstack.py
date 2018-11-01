# -*- coding: utf-8 -*-
"""Directory stack and associated utilities for the xonsh shell."""
import os
import glob
import argparse
import builtins
import subprocess

from xonsh.lazyasd import lazyobject
from xonsh.tools import get_sep
from xonsh.events import events
from xonsh.platform import ON_WINDOWS

DIRSTACK = []
"""A list containing the currently remembered directories."""
_unc_tempDrives = {}
""" drive: sharePath for temp drive letters we create for UNC mapping"""


def _unc_check_enabled() -> bool:
    r"""Check whether CMD.EXE is enforcing no-UNC-as-working-directory check.

    Check can be disabled by setting {HKCU, HKLM}/SOFTWARE\Microsoft\Command Processor\DisableUNCCheck:REG_DWORD=1

    Returns:
        True if `CMD.EXE` is enforcing the check (default Windows situation)
        False if check is explicitly disabled.
    """
    if not ON_WINDOWS:
        return

    import winreg

    wval = None

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, r"software\microsoft\command processor"
        )
        wval, wtype = winreg.QueryValueEx(key, "DisableUNCCheck")
        winreg.CloseKey(key)
    except OSError:
        pass

    if wval is None:
        try:
            key2 = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, r"software\microsoft\command processor"
            )
            wval, wtype = winreg.QueryValueEx(key2, "DisableUNCCheck")
            winreg.CloseKey(key2)
        except OSError as e:  # NOQA
            pass

    return False if wval else True


def _is_unc_path(some_path) -> bool:
    """True if path starts with 2 backward (or forward, due to python path hacking) slashes."""
    return (
        len(some_path) > 1
        and some_path[0] == some_path[1]
        and some_path[0] in (os.sep, os.altsep)
    )


def _unc_map_temp_drive(unc_path) -> str:
    r"""Map a new temporary drive letter for each distinct share,
    unless `CMD.EXE` is not insisting on non-UNC working directory.

    Emulating behavior of `CMD.EXE` `pushd`, create a new mapped drive (starting from Z: towards A:, skipping existing
     drive letters) for each new UNC path user selects.

    Args:
        unc_path: the path specified by user.  Assumed to be a UNC path of form \\<server>\share...

    Returns:
        a replacement for `unc_path` to be used as the actual new working directory.
        Note that the drive letter may be a the same as one already mapped if the server and share portion of `unc_path`
         is the same as one still active on the stack.
    """
    global _unc_tempDrives
    assert unc_path[1] in (os.sep, os.altsep), "unc_path is UNC form of path"

    if not _unc_check_enabled():
        return unc_path
    else:
        unc_share, rem_path = os.path.splitdrive(unc_path)
        unc_share = unc_share.casefold()
        for d in _unc_tempDrives:
            if _unc_tempDrives[d] == unc_share:
                return os.path.join(d, rem_path)

        for dord in range(ord("z"), ord("a"), -1):
            d = chr(dord) + ":"
            if not os.path.isdir(d):  # find unused drive letter starting from z:
                subprocess.check_output(
                    ["NET", "USE", d, unc_share], universal_newlines=True
                )
                _unc_tempDrives[d] = unc_share
                return os.path.join(d, rem_path)


def _unc_unmap_temp_drive(left_drive, cwd):
    """Unmap a temporary drive letter if it is no longer needed.
    Called after popping `DIRSTACK` and changing to new working directory, so we need stack *and*
    new current working directory to be sure drive letter no longer needed.

    Args:
        left_drive: driveletter (and colon) of working directory we just left
        cwd: full path of new current working directory
    """

    global _unc_tempDrives

    if left_drive not in _unc_tempDrives:  # if not one we've mapped, don't unmap it
        return

    for p in DIRSTACK + [cwd]:  # if still in use , don't unmap it.
        if p.casefold().startswith(left_drive):
            return

    _unc_tempDrives.pop(left_drive)
    subprocess.check_output(
        ["NET", "USE", left_drive, "/delete"], universal_newlines=True
    )


events.doc(
    "on_chdir",
    """
on_chdir(olddir: str, newdir: str) -> None

Fires when the current directory is changed for any reason.
""",
)


def _get_cwd():
    try:
        return os.getcwd()
    except (OSError, FileNotFoundError):
        return None


def _change_working_directory(newdir, follow_symlinks=False):
    env = builtins.__xonsh__.env
    old = env["PWD"]
    new = os.path.join(old, newdir)
    absnew = os.path.abspath(new)

    if follow_symlinks:
        absnew = os.path.realpath(absnew)

    try:
        os.chdir(absnew)
    except (OSError, FileNotFoundError):
        if new.endswith(get_sep()):
            new = new[:-1]
        if os.path.basename(new) == "..":
            env["PWD"] = new
    else:
        if old is not None:
            env["OLDPWD"] = old
        if new is not None:
            env["PWD"] = absnew

    # Fire event if the path actually changed
    if old != env["PWD"]:
        events.on_chdir.fire(olddir=old, newdir=env["PWD"])


def _try_cdpath(apath):
    # NOTE: this CDPATH implementation differs from the bash one.
    # In bash if a CDPATH is set, an unqualified local folder
    # is considered after all CDPATHs, example:
    # CDPATH=$HOME/src (with src/xonsh/ inside)
    # $ cd xonsh -> src/xonsh (with xonsh/xonsh)
    # a second $ cd xonsh has no effects, to move in the nested xonsh
    # in bash a full $ cd ./xonsh is needed.
    # In xonsh a relative folder is always preferred.
    env = builtins.__xonsh__.env
    cdpaths = env.get("CDPATH")
    for cdp in cdpaths:
        globber = builtins.__xonsh__.expand_path(os.path.join(cdp, apath))
        for cdpath_prefixed_path in glob.iglob(globber):
            return cdpath_prefixed_path
    return apath


def cd(args, stdin=None):
    """Changes the directory.

    If no directory is specified (i.e. if `args` is None) then this
    changes to the current user's home directory.
    """
    env = builtins.__xonsh__.env
    oldpwd = env.get("OLDPWD", None)
    cwd = env["PWD"]

    follow_symlinks = False
    if len(args) > 0 and args[0] == "-P":
        follow_symlinks = True
        del args[0]

    if len(args) == 0:
        d = os.path.expanduser("~")
    elif len(args) == 1:
        d = os.path.expanduser(args[0])
        if not os.path.isdir(d):
            if d == "-":
                if oldpwd is not None:
                    d = oldpwd
                else:
                    return "", "cd: no previous directory stored\n", 1
            elif d.startswith("-"):
                try:
                    num = int(d[1:])
                except ValueError:
                    return "", "cd: Invalid destination: {0}\n".format(d), 1
                if num == 0:
                    return None, None, 0
                elif num < 0:
                    return "", "cd: Invalid destination: {0}\n".format(d), 1
                elif num > len(DIRSTACK):
                    e = "cd: Too few elements in dirstack ({0} elements)\n"
                    return "", e.format(len(DIRSTACK)), 1
                else:
                    d = DIRSTACK[num - 1]
            else:
                d = _try_cdpath(d)
    else:
        return (
            "",
            (
                "cd takes 0 or 1 arguments, not {0}. An additional `-P` "
                "flag can be passed in first position to follow symlinks."
                "\n".format(len(args))
            ),
            1,
        )
    if not os.path.exists(d):
        return "", "cd: no such file or directory: {0}\n".format(d), 1
    if not os.path.isdir(d):
        return "", "cd: {0} is not a directory\n".format(d), 1
    if not os.access(d, os.X_OK):
        return "", "cd: permission denied: {0}\n".format(d), 1
    if (
        ON_WINDOWS
        and _is_unc_path(d)
        and _unc_check_enabled()
        and (not env.get("AUTO_PUSHD"))
    ):
        return (
            "",
            "cd: can't cd to UNC path on Windows, unless $AUTO_PUSHD set or reg entry "
            + r"HKCU\SOFTWARE\MICROSOFT\Command Processor\DisableUNCCheck:DWORD = 1"
            + "\n",
            1,
        )

    # now, push the directory onto the dirstack if AUTO_PUSHD is set
    if cwd is not None and env.get("AUTO_PUSHD"):
        pushd(["-n", "-q", cwd])
        if ON_WINDOWS and _is_unc_path(d):
            d = _unc_map_temp_drive(d)
    _change_working_directory(d, follow_symlinks)
    return None, None, 0


@lazyobject
def pushd_parser():
    parser = argparse.ArgumentParser(prog="pushd")
    parser.add_argument("dir", nargs="?")
    parser.add_argument(
        "-n",
        dest="cd",
        help="Suppresses the normal change of directory when"
        " adding directories to the stack, so that only the"
        " stack is manipulated.",
        action="store_false",
    )
    parser.add_argument(
        "-q",
        dest="quiet",
        help="Do not call dirs, regardless of $PUSHD_SILENT",
        action="store_true",
    )
    return parser


def pushd(args, stdin=None):
    r"""xonsh command: pushd

    Adds a directory to the top of the directory stack, or rotates the stack,
    making the new top of the stack the current working directory.

    On Windows, if the path is a UNC path (begins with `\\<server>\<share>`) and if the `DisableUNCCheck` registry
    value is not enabled, creates a temporary mapped drive letter and sets the working directory there, emulating
    behavior of `PUSHD` in `CMD.EXE`
    """
    global DIRSTACK

    try:
        args = pushd_parser.parse_args(args)
    except SystemExit:
        return None, None, 1

    env = builtins.__xonsh__.env

    pwd = env["PWD"]

    if env.get("PUSHD_MINUS", False):
        BACKWARD = "-"
        FORWARD = "+"
    else:
        BACKWARD = "+"
        FORWARD = "-"

    if args.dir is None:
        try:
            new_pwd = DIRSTACK.pop(0)
        except IndexError:
            e = "pushd: Directory stack is empty\n"
            return None, e, 1
    elif os.path.isdir(args.dir):
        new_pwd = args.dir
    else:
        try:
            num = int(args.dir[1:])
        except ValueError:
            e = "Invalid argument to pushd: {0}\n"
            return None, e.format(args.dir), 1

        if num < 0:
            e = "Invalid argument to pushd: {0}\n"
            return None, e.format(args.dir), 1

        if num > len(DIRSTACK):
            e = "Too few elements in dirstack ({0} elements)\n"
            return None, e.format(len(DIRSTACK)), 1
        elif args.dir.startswith(FORWARD):
            if num == len(DIRSTACK):
                new_pwd = None
            else:
                new_pwd = DIRSTACK.pop(len(DIRSTACK) - 1 - num)
        elif args.dir.startswith(BACKWARD):
            if num == 0:
                new_pwd = None
            else:
                new_pwd = DIRSTACK.pop(num - 1)
        else:
            e = "Invalid argument to pushd: {0}\n"
            return None, e.format(args.dir), 1
    if new_pwd is not None:
        if ON_WINDOWS and _is_unc_path(new_pwd):
            new_pwd = _unc_map_temp_drive(new_pwd)
        if args.cd:
            DIRSTACK.insert(0, os.path.expanduser(pwd))
            _change_working_directory(new_pwd)
        else:
            DIRSTACK.insert(0, os.path.expanduser(new_pwd))

    maxsize = env.get("DIRSTACK_SIZE")
    if len(DIRSTACK) > maxsize:
        DIRSTACK = DIRSTACK[:maxsize]

    if not args.quiet and not env.get("PUSHD_SILENT"):
        return dirs([], None)

    return None, None, 0


@lazyobject
def popd_parser():
    parser = argparse.ArgumentParser(prog="popd")
    parser.add_argument("dir", nargs="?")
    parser.add_argument(
        "-n",
        dest="cd",
        help="Suppresses the normal change of directory when"
        " adding directories to the stack, so that only the"
        " stack is manipulated.",
        action="store_false",
    )
    parser.add_argument(
        "-q",
        dest="quiet",
        help="Do not call dirs, regardless of $PUSHD_SILENT",
        action="store_true",
    )
    return parser


def popd(args, stdin=None):
    """
    xonsh command: popd

    Removes entries from the directory stack.
    """
    global DIRSTACK

    try:
        args = pushd_parser.parse_args(args)
    except SystemExit:
        return None, None, 1

    env = builtins.__xonsh__.env

    if env.get("PUSHD_MINUS"):
        BACKWARD = "-"
        FORWARD = "+"
    else:
        BACKWARD = "-"
        FORWARD = "+"

    if args.dir is None:
        try:
            new_pwd = DIRSTACK.pop(0)
        except IndexError:
            e = "popd: Directory stack is empty\n"
            return None, e, 1
    else:
        try:
            num = int(args.dir[1:])
        except ValueError:
            e = "Invalid argument to popd: {0}\n"
            return None, e.format(args.dir), 1

        if num < 0:
            e = "Invalid argument to popd: {0}\n"
            return None, e.format(args.dir), 1

        if num > len(DIRSTACK):
            e = "Too few elements in dirstack ({0} elements)\n"
            return None, e.format(len(DIRSTACK)), 1
        elif args.dir.startswith(FORWARD):
            if num == len(DIRSTACK):
                new_pwd = DIRSTACK.pop(0)
            else:
                new_pwd = None
                DIRSTACK.pop(len(DIRSTACK) - 1 - num)
        elif args.dir.startswith(BACKWARD):
            if num == 0:
                new_pwd = DIRSTACK.pop(0)
            else:
                new_pwd = None
                DIRSTACK.pop(num - 1)
        else:
            e = "Invalid argument to popd: {0}\n"
            return None, e.format(args.dir), 1

    if new_pwd is not None:
        e = None
        if args.cd:
            env = builtins.__xonsh__.env
            pwd = env["PWD"]

            _change_working_directory(new_pwd)

            if ON_WINDOWS:
                drive, rem_path = os.path.splitdrive(pwd)
                _unc_unmap_temp_drive(drive.casefold(), new_pwd)

    if not args.quiet and not env.get("PUSHD_SILENT"):
        return dirs([], None)

    return None, None, 0


@lazyobject
def dirs_parser():
    parser = argparse.ArgumentParser(prog="dirs")
    parser.add_argument("N", nargs="?")
    parser.add_argument(
        "-c",
        dest="clear",
        help="Clears the directory stack by deleting all of" " the entries.",
        action="store_true",
    )
    parser.add_argument(
        "-p",
        dest="print_long",
        help="Print the directory stack with one entry per" " line.",
        action="store_true",
    )
    parser.add_argument(
        "-v",
        dest="verbose",
        help="Print the directory stack with one entry per"
        " line, prefixing each entry with its index in the"
        " stack.",
        action="store_true",
    )
    parser.add_argument(
        "-l",
        dest="long",
        help="Produces a longer listing; the default listing"
        " format uses a tilde to denote the home directory.",
        action="store_true",
    )
    return parser


def dirs(args, stdin=None):
    """xonsh command: dirs

    Displays the list of currently remembered directories.  Can also be used
    to clear the directory stack.
    """
    global DIRSTACK
    try:
        args = dirs_parser.parse_args(args)
    except SystemExit:
        return None, None

    env = builtins.__xonsh__.env
    dirstack = [os.path.expanduser(env["PWD"])] + DIRSTACK

    if env.get("PUSHD_MINUS"):
        BACKWARD = "-"
        FORWARD = "+"
    else:
        BACKWARD = "-"
        FORWARD = "+"

    if args.clear:
        DIRSTACK = []
        return None, None, 0

    if args.long:
        o = dirstack
    else:
        d = os.path.expanduser("~")
        o = [i.replace(d, "~") for i in dirstack]

    if args.verbose:
        out = ""
        pad = len(str(len(o) - 1))
        for (ix, e) in enumerate(o):
            blanks = " " * (pad - len(str(ix)))
            out += "\n{0}{1} {2}".format(blanks, ix, e)
        out = out[1:]
    elif args.print_long:
        out = "\n".join(o)
    else:
        out = " ".join(o)

    N = args.N
    if N is not None:
        try:
            num = int(N[1:])
        except ValueError:
            e = "Invalid argument to dirs: {0}\n"
            return None, e.format(N), 1

        if num < 0:
            e = "Invalid argument to dirs: {0}\n"
            return None, e.format(len(o)), 1

        if num >= len(o):
            e = "Too few elements in dirstack ({0} elements)\n"
            return None, e.format(len(o)), 1

        if N.startswith(BACKWARD):
            idx = num
        elif N.startswith(FORWARD):
            idx = len(o) - 1 - num
        else:
            e = "Invalid argument to dirs: {0}\n"
            return None, e.format(N), 1

        out = o[idx]

    return out + "\n", None, 0
