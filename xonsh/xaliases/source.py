import os

from xonsh.built_ins import XSH
from xonsh.environ import locate_binary, make_args_env
from xonsh.tools import print_color, swap_values, unthreadable


@unthreadable
def source(args, stdin=None, stdout=None, stderr=None):
    """Executes the contents of the provided files in the current context.
    If sourced file isn't found in cwd, search for file along $PATH to source
    instead.
    """
    env = XSH.env
    encoding = env.get("XONSH_ENCODING")
    errors = env.get("XONSH_ENCODING_ERRORS")
    for i, fname in enumerate(args):
        fpath = fname
        if not os.path.isfile(fpath):
            fpath = locate_binary(fname)
            if fpath is None:
                if env.get("XONSH_DEBUG"):
                    print(f"source: {fname}: No such file", file=stderr)
                if i == 0:
                    raise RuntimeError(
                        "must source at least one file, " + fname + " does not exist."
                    )
                break
        _, fext = os.path.splitext(fpath)
        if fext and fext != ".xsh" and fext != ".py":
            raise RuntimeError(
                "attempting to source non-xonsh file! If you are "
                "trying to source a file in another language, "
                "then please use the appropriate source command. "
                "For example, source-bash script.sh"
            )
        with open(fpath, encoding=encoding, errors=errors) as fp:
            src = fp.read()
        if not src.endswith("\n"):
            src += "\n"
        ctx = XSH.ctx
        updates = {"__file__": fpath, "__name__": os.path.abspath(fpath)}
        with env.swap(**make_args_env(args[i + 1 :])), swap_values(ctx, updates):
            try:
                XSH.builtins.execx(src, "exec", ctx, filename=fpath)
            except Exception:
                print_color(
                    "{RED}You may be attempting to source non-xonsh file! "
                    "{RESET}If you are trying to source a file in "
                    "another language, then please use the appropriate "
                    "source command. For example, {GREEN}source-bash "
                    "script.sh{RESET}",
                    file=stderr,
                )
                raise
