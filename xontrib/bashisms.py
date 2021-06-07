"""Bash-like interface extensions for xonsh."""
import shlex
import sys
import re
from xonsh.built_ins import XSH

__all__ = ()


def _warn_not_supported(msg: str):
    print(
        f"""Not supported ``{msg}`` in xontrib bashisms.
PRs are welcome - https://github.com/xonsh/xonsh/blob/main/xontrib/bashisms.py""",
        file=sys.stderr,
    )


@XSH.builtins.events.on_transform_command
def bash_preproc(cmd, **kw):
    bang_previous = {
        "!": lambda x: x,
        "$": lambda x: shlex.split(x)[-1],
        "^": lambda x: shlex.split(x)[0],
        "*": lambda x: " ".join(shlex.split(x)[1:]),
    }

    def replace_bang(m):
        arg = m.group(1)
        inputs = XSH.history.inps

        # Dissect the previous command.
        if arg in bang_previous:
            try:
                return bang_previous[arg](inputs[-1])
            except IndexError:
                print("xonsh: no history for '!{}'".format(arg))
                return ""

        # Look back in history for a matching command.
        else:
            try:
                return next((x for x in reversed(inputs) if x.startswith(arg)))
            except StopIteration:
                print("xonsh: no previous commands match '!{}'".format(arg))
                return ""

    return re.sub(r"!([!$^*]|[\w]+)", replace_bang, cmd)


def alias(args, stdin=None):
    ret = 0

    if args:
        for arg in args:
            if "=" in arg:
                # shlex.split to remove quotes, e.g. "foo='echo hey'" into
                # "foo=echo hey"
                name, cmd = shlex.split(arg)[0].split("=", 1)
                XSH.aliases[name] = shlex.split(cmd)
            elif arg in XSH.aliases:
                print("{}={}".format(arg, XSH.aliases[arg]))
            else:
                print("alias: {}: not found".format(arg), file=sys.stderr)
                ret = 1
    else:
        for alias, cmd in XSH.aliases.items():
            print("{}={}".format(alias, cmd))

    return ret


XSH.aliases["alias"] = alias
XSH.env["THREAD_SUBPROCS"] = False


def _unset(args):
    if not args:
        print("Usage: unset ENV_VARIABLE", file=sys.stderr)

    for v in args:
        try:
            XSH.env.pop(v)
        except KeyError:
            print(f"{v} not found", file=sys.stderr)


XSH.aliases["unset"] = _unset


def _export(args):
    if not args:
        print("Usage: export ENV_VARIABLE=VALUE", file=sys.stderr)

    for eq in args:
        if "=" in eq:
            name, val = shlex.split(eq)[0].split("=", 1)
            XSH.env[name] = val
        else:
            print(f"{eq} equal sign not found", file=sys.stderr)


XSH.aliases["export"] = _export


def _set(args):
    arg = args[0]
    if arg == "-e":
        XSH.env["RAISE_SUBPROC_ERROR"] = True
    elif arg == "+e":
        XSH.env["RAISE_SUBPROC_ERROR"] = False
    elif arg == "-x":
        XSH.env["XONSH_TRACE_SUBPROC"] = True
    elif arg == "+x":
        XSH.env["XONSH_TRACE_SUBPROC"] = False
    else:
        _warn_not_supported(f"set {arg}")


XSH.aliases["set"] = _set


def _shopt(args):

    supported_shopt = ["DOTGLOB"]

    args_len = len(args)
    if args_len == 0:
        for so in supported_shopt:
            onoff = "on" if so in XSH.env and XSH.env[so] else "off"
            print(f"dotglob\t{onoff}")
        return
    elif args_len < 2 or args[0] in ["-h", "--help"]:
        print(f'Usage: shopt <-s|-u> <{"|".join(supported_shopt).lower()}>')
        return

    opt = args[0]
    optname = args[1]

    if opt == "-s" and optname == "dotglob":
        XSH.env["DOTGLOB"] = True
    elif opt == "-u" and optname == "dotglob":
        XSH.env["DOTGLOB"] = False
    else:
        _warn_not_supported(f"shopt {args}")


XSH.aliases["shopt"] = _shopt


XSH.aliases["complete"] = "completer list"
