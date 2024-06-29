"""The xonsh shell"""

import difflib
import sys
import time
import warnings

import xonsh.history.main as xhm
from xonsh.built_ins import XSH
from xonsh.events import events
from xonsh.history.dummy import DummyHistory
from xonsh.platform import (
    best_shell_type,
    has_prompt_toolkit,
    minimum_required_ptk_version,
    ptk_above_min_supported,
)
from xonsh.tools import XonshError, is_class, print_exception, simple_random_choice

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
    "on_command_not_found",
    """
on_command_not_found(cmd: list[str]) -> None

Fires if a command is not found (only in interactive sessions).

Parameters:

* ``cmd``: The command that was attempted
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


class Shell:
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
                    "'prompt-toolkit' python package is not installed. Falling back to readline.",
                    stacklevel=2,
                )
                shell_type = "readline"
            elif not ptk_above_min_supported():
                warnings.warn(
                    "Installed prompt-toolkit version < v{}.{}.{} is not ".format(
                        *minimum_required_ptk_version
                    )
                    + "supported. Falling back to readline.",
                    stacklevel=2,
                )
                shell_type = "readline"
            if init_shell_type in ("ptk1", "prompt_toolkit1"):
                warnings.warn(
                    f"$SHELL_TYPE='{init_shell_type}' now deprecated, please update your run control file'",
                    stacklevel=2,
                )
        return shell_type

    @staticmethod
    def construct_shell_cls(backend, **kwargs):
        """Construct the history backend object."""
        if is_class(backend):
            cls = backend
        else:
            """
            There is an edge case that we're using mostly in integration tests:
            `echo 'echo 1' | xonsh -i` and it's not working with `TERM=dumb` (#5462 #5517)
            because `dumb` is readline where stdin is not supported yet. PR is very welcome!
            So in this case we need to force using prompt_toolkit.
            """
            is_stdin_to_interactive = (
                XSH.env.get("XONSH_INTERACTIVE", False) and not sys.stdin.isatty()
            )

            if backend == "none":
                from xonsh.shells.base_shell import BaseShell as cls
            elif backend == "prompt_toolkit" or is_stdin_to_interactive:
                from xonsh.shells.ptk_shell import PromptToolkitShell as cls
            elif backend == "readline":
                from xonsh.shells.readline_shell import ReadlineShell as cls
            elif backend == "dumb":
                from xonsh.shells.dumb_shell import DumbShell as cls
            else:
                raise XonshError(f"{backend} is not recognized as a shell type")
        return cls(**kwargs)

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

        self.shell = self.construct_shell_cls(
            shell_type, execer=self.execer, ctx=self.ctx, **kwargs
        )
        # allows history garbage collector to start running
        if hist.gc is not None:
            hist.gc.wait_for_shell = False

    def __getattr__(self, attr):
        """Delegates calls to appropriate shell instance."""
        return getattr(self.shell, attr)
