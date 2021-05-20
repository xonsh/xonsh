import os
import re
import pickle
import subprocess
import typing as tp

from xonsh.parsers.completion_context import CommandContext
from xonsh.built_ins import XSH
import xonsh.lazyasd as xl

from xonsh.completers.tools import get_filter_function, contextual_command_completer

OPTIONS: tp.Optional[tp.Dict[str, tp.Any]] = None
OPTIONS_PATH: tp.Optional[str] = None


@xl.lazyobject
def SCRAPE_RE():
    return re.compile(r"^(?:\s*(?:-\w|--[a-z0-9-]+)[\s,])+", re.M)


@xl.lazyobject
def INNER_OPTIONS_RE():
    return re.compile(r"-\w|--[a-z0-9-]+")


@contextual_command_completer
def complete_from_man(context: CommandContext):
    """
    Completes an option name, based on the contents of the associated man
    page.
    """
    global OPTIONS, OPTIONS_PATH
    if OPTIONS is None:
        datadir: str = XSH.env["XONSH_DATA_DIR"]  # type: ignore
        OPTIONS_PATH = os.path.join(datadir, "man_completions_cache")
        try:
            with open(OPTIONS_PATH, "rb") as f:
                OPTIONS = pickle.load(f)
        except Exception:
            OPTIONS = {}
    if context.arg_index == 0 or not context.prefix.startswith("-"):
        return set()
    cmd = context.args[0].value
    if cmd not in OPTIONS:
        try:
            manpage = subprocess.Popen(
                ["man", cmd], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
            )
            # This is a trick to get rid of reverse line feeds
            enc_text = subprocess.check_output(["col", "-b"], stdin=manpage.stdout)
            text = enc_text.decode("utf-8")
            scraped_text = " ".join(SCRAPE_RE.findall(text))
            matches = INNER_OPTIONS_RE.findall(scraped_text)
            OPTIONS[cmd] = matches
            with open(tp.cast(str, OPTIONS_PATH), "wb") as f:
                pickle.dump(OPTIONS, f)
        except Exception:
            return set()
    return {s for s in OPTIONS[cmd] if get_filter_function()(s, context.prefix)}
