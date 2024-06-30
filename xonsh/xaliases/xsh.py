import os
import sys

from xonsh.built_ins import XSH
from xonsh.cli_utils import Annotated, Arg, ArgParserAlias
from xonsh.tools import (
    adjust_shlvl,
    to_shlvl,
)


def xonsh_reset(args, stdin=None):
    """Clears __xonsh__.ctx"""
    XSH.ctx.clear()


def xexec_fn(
    command: Annotated[list[str], Arg(nargs="...")],
    login=False,
    clean=False,
    name="",
    _stdin=None,
):
    """exec (also aliased as xexec) uses the os.execvpe() function to
    replace the xonsh process with the specified program.

    This provides the functionality of the bash 'exec' builtin::

        >>> exec bash -l -i
        bash $

    Parameters
    ----------
    command
        program to launch along its arguments
    login : -l, --login
        the shell places a dash at the
        beginning of the zeroth argument passed to command to simulate login
        shell.
    clean : -c, --clean
        causes command to be executed with an empty environment.
    name : -a, --name
        the shell passes name as the zeroth argument
        to the executed command.

    Notes
    -----
    This command **is not** the same as the Python builtin function
    exec(). That function is for running Python code. This command,
    which shares the same name as the sh-lang statement, is for launching
    a command directly in the same process. In the event of a name conflict,
    please use the xexec command directly or dive into subprocess mode
    explicitly with ![exec command]. For more details, please see
    http://xon.sh/faq.html#exec.
    """
    if len(command) == 0:
        return (None, "xonsh: exec: no command specified\n", 1)

    cmd = command[0]
    if name:
        command[0] = name
    if login:
        command[0] = f"-{command[0]}"

    denv = {}
    if not clean:
        denv = XSH.env.detype()

        # decrement $SHLVL to mirror bash's behaviour
        if "SHLVL" in denv:
            old_shlvl = to_shlvl(denv["SHLVL"])
            denv["SHLVL"] = str(adjust_shlvl(old_shlvl, -1))

    try:
        os.execvpe(cmd, command, denv)
    except FileNotFoundError as e:
        return (
            None,
            f"xonsh: exec: file not found: {e.args[1]}: {command[0]}" "\n",
            1,
        )


xexec = ArgParserAlias(func=xexec_fn, has_args=True, prog="xexec")


def showcmd_fn(cmd: Annotated[list[str], Arg(nargs="...")]):
    """
    Displays the command and arguments as a list of strings that xonsh would
    run in subprocess mode. Useful determining how xonsh evaluates
    your commands and arguments prior to running these commands.

    Parameters
    ----------
    cmd
        program to launch along its arguments

    Examples
    --------
      $ showcmd echo $USER "can't" hear "the sea"
      ['echo', 'I', "can't", 'hear', 'the sea']
    """
    sys.displayhook(cmd)


showcmd = ArgParserAlias(func=showcmd_fn, has_args=True, prog="showcmd")
