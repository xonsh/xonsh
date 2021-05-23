# -*- coding: utf-8 -*-
"""The xonsh shell"""
import sys
import time
import difflib
import warnings

from xonsh.platform import (
    best_shell_type,
    ptk_above_min_supported,
    has_prompt_toolkit,
    minimum_required_ptk_version,
)
from xonsh.tools import XonshError, print_exception, simple_random_choice
from xonsh.events import events
from xonsh.history.dummy import DummyHistory
import xonsh.history.main as xhm
from xonsh.built_ins import XSH

events.doc(
    "on_transform_command",
    """
on_transform_command(cmd: str) -> str

Fired to request xontribs to transform a command line. Return the transformed
command, or the same command if no transformation occurs. Only done for
interactive sessions.

This may be fired multiple times per command, with other transformers input or
output, so design any handlers for this carefully.
""",
)

events.doc(
    "on_precommand",
    """
on_precommand(cmd: str) -> None

Fires just before a command is executed.
""",
)

events.doc(
    "on_postcommand",
    """
on_postcommand(cmd: str, rtn: int, out: str or None, ts: list) -> None

Fires just after a command is executed. The arguments are the same as history.

Parameters:

* ``cmd``: The command that was executed (after transformation)
* ``rtn``: The result of the command executed (``0`` for success)
* ``out``: If xonsh stores command output, this is the output
* ``ts``: Timestamps, in the order of ``[starting, ending]``
""",
)

events.doc(
    "on_pre_prompt_format",
    """
on_pre_prompt_format() -> None

Fires before the prompt will be formatted
""",
)

events.doc(
    "on_pre_prompt",
    """
on_pre_prompt() -> None

Fires just before showing the prompt
""",
)


events.doc(
    "on_post_prompt",
    """
on_post_prompt() -> None

Fires just after the prompt returns
""",
)


def transform_command(src, show_diff=True):
    """Returns the results of firing the precommand handles."""
    i = 0
    limit = sys.getrecursionlimit()
    lst = ""
    raw = src
    while src != lst:
        lst = src
        srcs = events.on_transform_command.fire(cmd=src)
        for s in srcs:
            if s != lst:
                src = s
                break
        i += 1
        if i == limit:
            print_exception(
                "Modifications to source input took more than "
                "the recursion limit number of iterations to "
                "converge."
            )
    debug_level = XSH.env.get("XONSH_DEBUG")
    if show_diff and debug_level >= 1 and src != raw:
        sys.stderr.writelines(
            difflib.unified_diff(
                raw.splitlines(keepends=True),
                src.splitlines(keepends=True),
                fromfile="before precommand event",
                tofile="after precommand event",
            )
        )
    return src


class Shell(object):
    """Main xonsh shell.

    Initializes execution environment and decides if prompt_toolkit or
    readline version of shell should be used.
    """

    shell_type_aliases = {
        "b": "best",
        "best": "best",
        "d": "dumb",
        "dumb": "dumb",
        "ptk": "prompt_toolkit",  # there's only 1 prompt_toolkit shell (now)
        "prompt-toolkit": "prompt_toolkit",
        "prompt_toolkit": "prompt_toolkit",
        "rand": "random",
        "random": "random",
        "rl": "readline",
        "readline": "readline",
    }

    @staticmethod
    def choose_shell_type(init_shell_type=None, env=None):
        # pick a valid shell -- if no shell is specified by the user,
        # shell type is pulled from env
        # extracted for testability
        shell_type = init_shell_type
        if shell_type is None and env:
            shell_type = env.get("SHELL_TYPE")
            if shell_type == "none":
                # This bricks interactive xonsh
                # Can happen from the use of .xinitrc, .xsession, etc
                # odd logic.  We don't override if shell.__init__( shell_type="none"),
                # only if it come from environment?
                shell_type = "best"
        shell_type = Shell.shell_type_aliases.get(shell_type, shell_type)
        if shell_type == "best" or shell_type is None:
            shell_type = best_shell_type()
        elif env and env.get("TERM", "") == "dumb":
            shell_type = "dumb"
        elif shell_type == "random":
            shell_type = simple_random_choice(("readline", "prompt_toolkit"))
        if shell_type == "prompt_toolkit":
            if not has_prompt_toolkit():
                warnings.warn(
                    "'prompt-toolkit' python package is not installed. Falling back to readline."
                )
                shell_type = "readline"
            elif not ptk_above_min_supported():
                warnings.warn(
                    "Installed prompt-toolkit version < v{}.{}.{} is not ".format(
                        *minimum_required_ptk_version
                    )
                    + "supported. Falling back to readline."
                )
                shell_type = "readline"
            if init_shell_type in ("ptk1", "prompt_toolkit1"):
                warnings.warn(
                    "$SHELL_TYPE='{}' now deprecated, please update your run control file'".format(
                        init_shell_type
                    )
                )
        return shell_type

    def __init__(self, execer, ctx=None, shell_type=None, **kwargs):
        """
        Parameters
        ----------
        execer : Execer
            An execer instance capable of running xonsh code.
        ctx : Mapping, optional
            The execution context for the shell (e.g. the globals namespace).
            If none, this is computed by loading the rc files. If not None,
            this no additional context is computed and this is used
            directly.
        shell_type : str, optional
            The shell type to start, such as 'readline', 'prompt_toolkit1',
            or 'random'.
        """
        self.execer = execer
        self.ctx = {} if ctx is None else ctx
        env = XSH.env

        # build history backend before creating shell
        if env.get("XONSH_INTERACTIVE"):
            XSH.history = hist = xhm.construct_history(
                env=env.detype(),
                ts=[time.time(), None],
                locked=True,
                filename=env.get("XONSH_HISTORY_FILE", None),
            )
            env["XONSH_HISTORY_FILE"] = hist.filename
        else:
            XSH.history = hist = DummyHistory()
            env["XONSH_HISTORY_FILE"] = None

        shell_type = self.choose_shell_type(shell_type, env)

        self.shell_type = env["SHELL_TYPE"] = shell_type

        # actually make the shell
        if shell_type == "none":
            from xonsh.base_shell import BaseShell as shell_class
        elif shell_type == "prompt_toolkit":
            from xonsh.ptk_shell.shell import PromptToolkitShell as shell_class
        elif shell_type == "readline":
            from xonsh.readline_shell import ReadlineShell as shell_class
        elif shell_type == "jupyter":
            from xonsh.jupyter_shell import JupyterShell as shell_class
        elif shell_type == "dumb":
            from xonsh.dumb_shell import DumbShell as shell_class
        else:
            raise XonshError("{} is not recognized as a shell type".format(shell_type))
        self.shell = shell_class(execer=self.execer, ctx=self.ctx, **kwargs)
        # allows history garbage collector to start running
        if hist.gc is not None:
            hist.gc.wait_for_shell = False

    def __getattr__(self, attr):
        """Delegates calls to appropriate shell instance."""
        return getattr(self.shell, attr)
