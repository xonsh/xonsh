"""Windows only xontrib, to release the lock on the current directory whenever the prompt is shown.

Enabling this will allow other programs or
Windows Explorer to delete or rename the current or parent
directories. Internally, it is accomplished by temporarily resetting
CWD to the root drive folder while waiting at the prompt. This only
works with the prompt_toolkit backend and can cause issues
if any extensions are enabled that hook the prompt and relies on
``os.getcwd()``.
"""
import functools
import os
from pathlib import Path

from xonsh.built_ins import XSH, XonshSession
from xonsh.platform import ON_CYGWIN, ON_MSYS, ON_WINDOWS
from xonsh.tools import print_exception


def _chdir_up(path):
    """Change directory to path or if path does not exist
    the first valid parent.
    """
    path = Path(path)
    try:
        os.chdir(path)
        return str(path.absolute())
    except (FileNotFoundError, NotADirectoryError):
        path.resolve()
        return _chdir_up(path.parent)


def _cwd_release_wrapper(func):
    """Decorator for Windows to wrap the prompt function and release
    the process lock on the current directory while the prompt is
    displayed. This works by temporarily setting
    the workdir to the users home directory.
    """
    env = XSH.env
    if env.get("UPDATE_PROMPT_ON_KEYPRESS"):
        return func if not hasattr(func, "_orgfunc") else func._orgfunc

    if hasattr(func, "_orgfunc"):
        # Already wrapped
        return func
    else:

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            anchor = Path(os.getcwd()).anchor
            os.chdir(anchor)
            try:
                out = func(*args, **kwargs)
            finally:
                try:
                    pwd = env.get("PWD", anchor)
                    os.chdir(pwd)
                except (FileNotFoundError, NotADirectoryError):
                    print_exception()
                    newpath = _chdir_up(pwd)
                    XSH.env["PWD"] = newpath
                    raise KeyboardInterrupt
            return out

        wrapper._orgfunc = func
        return wrapper


def _cwd_restore_wrapper(func):
    """Decorator for Windows which will temporary restore the true working
    directory. Designed to wrap completer callbacks from the
    prompt_toolkit or readline.
    """
    env = XSH.env
    if env.get("UPDATE_PROMPT_ON_KEYPRESS"):
        return func if not hasattr(func, "_orgfunc") else func._orgfunc

    if hasattr(func, "_orgfunc"):
        # Already wrapped
        return func
    else:

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            workdir = os.getcwd()
            _chdir_up(env.get("PWD", workdir))
            out = func(*args, **kwargs)
            _chdir_up(workdir)
            return out

        wrapper._orgfunc = func
        return wrapper


def setup_release_cwd_hook(prompter, history, completer, bindings, **kw):
    if ON_WINDOWS and not ON_CYGWIN and not ON_MSYS:
        prompter.prompt = _cwd_release_wrapper(prompter.prompt)
        if completer.completer:
            # Temporarily restore cwd for callbacks to the completer
            completer.completer.complete = _cwd_restore_wrapper(
                completer.completer.complete
            )


def _load_xontrib_(xsh: XonshSession, **_):
    xsh.builtins.events.on_ptk_create(_cwd_restore_wrapper)
