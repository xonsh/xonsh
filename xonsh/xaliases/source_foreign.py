import functools
import os
from typing import Annotated

from xonsh.built_ins import XSH
from xonsh.cli_utils import Arg, ArgParserAlias
from xonsh.environ import locate_binary
from xonsh.foreign_shells import foreign_shell_data
from xonsh.tools import argvquote, escape_windows_cmd_string


def source_foreign(
    shell: str,
    files_or_code: Annotated[list[str], Arg(nargs="+")],
    interactive=False,
    login=False,
    envcmd=None,
    aliascmd=None,
    extra_args="",
    safe=True,
    prevcmd="",
    postcmd="",
    funcscmd="",
    sourcer=None,
    use_tmpfile=False,
    seterrprevcmd=None,
    seterrpostcmd=None,
    overwrite_aliases=False,
    suppress_skip_message=False,
    show=False,
    dryrun=False,
    _stderr=None,
):
    """Sources a file written in a foreign shell language.

    Parameters
    ----------
    shell
        Name or path to the foreign shell
    files_or_code
        file paths to source or code in the target language.
    interactive : -i, --interactive
        whether the sourced shell should be interactive
    login : -l, --login
        whether the sourced shell should be login
    envcmd : --envcmd
        command to print environment
    aliascmd : --aliascmd
        command to print aliases
    extra_args : --extra-args
        extra arguments needed to run the shell
    safe : -u, --unsafe
        whether the source shell should be run safely, and not raise any errors, even if they occur.
    prevcmd : -p, --prevcmd
        command(s) to run before any other commands, replaces traditional source.
    postcmd : --postcmd
        command(s) to run after all other commands
    funcscmd : --funcscmd
        code to find locations of all native functions in the shell language.
    sourcer : --sourcer
        the source command in the target shell language.
        If this is not set, a default value will attempt to be
        looked up based on the shell name.
    use_tmpfile : --use-tmpfile
        whether the commands for source shell should be written to a temporary file.
    seterrprevcmd : --seterrprevcmd
        command(s) to set exit-on-error before any other commands.
    seterrpostcmd : --seterrpostcmd
        command(s) to set exit-on-error after all other commands.
    overwrite_aliases : --overwrite-aliases
        flag for whether or not sourced aliases should replace the current xonsh aliases.
    suppress_skip_message : --suppress-skip-message
        flag for whether or not skip messages should be suppressed.
    show : --show
        show the script output.
    dryrun : -d, --dry-run
        Will not actually source the file.
    """
    extra_args = tuple(extra_args.split())
    env = XSH.env
    suppress_skip_message = (
        env.get("FOREIGN_ALIASES_SUPPRESS_SKIP_MESSAGE")
        if not suppress_skip_message
        else suppress_skip_message
    )
    files: tuple[str, ...] = ()
    if prevcmd:
        pass  # don't change prevcmd if given explicitly
    elif os.path.isfile(files_or_code[0]):
        if not sourcer:
            return (None, "xonsh: error: `sourcer` command is not mentioned.\n", 1)
        # we have filenames to source
        prevcmd = "".join([f"{sourcer} {f}\n" for f in files_or_code])
        files = tuple(files_or_code)
    elif not prevcmd:
        prevcmd = " ".join(files_or_code)  # code to run, no files
    foreign_shell_data.cache_clear()  # make sure that we don't get prev src
    fsenv, fsaliases = foreign_shell_data(
        shell=shell,
        login=login,
        interactive=interactive,
        envcmd=envcmd,
        aliascmd=aliascmd,
        extra_args=extra_args,
        safe=safe,
        prevcmd=prevcmd,
        postcmd=postcmd,
        funcscmd=funcscmd or None,  # the default is None in the called function
        sourcer=sourcer,
        use_tmpfile=use_tmpfile,
        seterrprevcmd=seterrprevcmd,
        seterrpostcmd=seterrpostcmd,
        show=show,
        dryrun=dryrun,
        files=files,
    )
    if fsenv is None:
        if dryrun:
            return
        else:
            msg = f"xonsh: error: Source failed: {prevcmd!r}\n"
            msg += "xonsh: error: Possible reasons: File not found or syntax error\n"
            return (None, msg, 1)
    # apply results
    denv = env.detype()
    for k, v in fsenv.items():
        if k == "SHLVL":  # ignore $SHLVL as sourcing should not change $SHLVL
            continue
        if k in denv and v == denv[k]:
            continue  # no change from original
        env[k] = v
    # Remove any env-vars that were unset by the script.
    for k in denv:
        if k not in fsenv:
            env.pop(k, None)
    # Update aliases
    baliases = XSH.aliases
    for k, v in fsaliases.items():
        if k in baliases and v == baliases[k]:
            continue  # no change from original
        elif overwrite_aliases or k not in baliases:
            baliases[k] = v
        elif suppress_skip_message:
            pass
        else:
            msg = (
                "Skipping application of {0!r} alias from {1!r} "
                "since it shares a name with an existing xonsh alias. "
                'Use "--overwrite-alias" option to apply it anyway. '
                'You may prevent this message with "--suppress-skip-message" or '
                '"$FOREIGN_ALIASES_SUPPRESS_SKIP_MESSAGE = True".'
            )
            print(msg.format(k, shell), file=_stderr)


class SourceForeignAlias(ArgParserAlias):
    def build(self):
        parser = self.create_parser(**self.kwargs)
        # for backwards compatibility
        parser.add_argument(
            "-n",
            "--non-interactive",
            action="store_false",
            dest="interactive",
            help="Deprecated: The default mode runs in non-interactive mode.",
        )
        return parser


alias = SourceForeignAlias(func=source_foreign, has_args=True)

bash = SourceForeignAlias(
    func=functools.partial(source_foreign, "bash", sourcer="source"),
    has_args=True,
    prog="source-bash",
)
zsh = SourceForeignAlias(
    func=functools.partial(source_foreign, "zsh", sourcer="source"),
    has_args=True,
    prog="source-zsh",
)


def source_cmd_fn(
    files: Annotated[list[str], Arg(nargs="+")],
    login=False,
    aliascmd=None,
    extra_args="",
    safe=True,
    postcmd="",
    funcscmd="",
    seterrprevcmd=None,
    overwrite_aliases=False,
    suppress_skip_message=False,
    show=False,
    dryrun=False,
    _stderr=None,
):
    """
        Source cmd.exe files

    Parameters
    ----------
    files
        paths to source files.
    login : -l, --login
        whether the sourced shell should be login
    envcmd : --envcmd
        command to print environment
    aliascmd : --aliascmd
        command to print aliases
    extra_args : --extra-args
        extra arguments needed to run the shell
    safe : -s, --safe
        whether the source shell should be run safely, and not raise any errors, even if they occur.
    postcmd : --postcmd
        command(s) to run after all other commands
    funcscmd : --funcscmd
        code to find locations of all native functions in the shell language.
    seterrprevcmd : --seterrprevcmd
        command(s) to set exit-on-error before any other commands.
    overwrite_aliases : --overwrite-aliases
        flag for whether or not sourced aliases should replace the current xonsh aliases.
    suppress_skip_message : --suppress-skip-message
        flag for whether or not skip messages should be suppressed.
    show : --show
        show the script output.
    dryrun : -d, --dry-run
        Will not actually source the file.
    """
    args = list(files)
    fpath = locate_binary(args[0])
    args[0] = fpath if fpath else args[0]
    if not os.path.isfile(args[0]):
        return (None, f"xonsh: error: File not found: {args[0]}\n", 1)
    prevcmd = "call "
    prevcmd += " ".join([argvquote(arg, force=True) for arg in args])
    prevcmd = escape_windows_cmd_string(prevcmd)
    with XSH.env.swap(PROMPT="$P$G"):
        return source_foreign(
            shell="cmd",
            files_or_code=args,
            interactive=True,
            sourcer="call",
            envcmd="set",
            seterrpostcmd="if errorlevel 1 exit 1",
            use_tmpfile=True,
            prevcmd=prevcmd,
            #     from this function
            login=login,
            aliascmd=aliascmd,
            extra_args=extra_args,
            safe=safe,
            postcmd=postcmd,
            funcscmd=funcscmd,
            seterrprevcmd=seterrprevcmd,
            overwrite_aliases=overwrite_aliases,
            suppress_skip_message=suppress_skip_message,
            show=show,
            dryrun=dryrun,
        )


cmd = ArgParserAlias(func=source_cmd_fn, has_args=True, prog="source-cmd")
