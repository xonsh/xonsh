import functools
import json
import os
import re
import pickle
import subprocess
import textwrap
import typing as tp
from pathlib import Path

from xonsh.parsers.completion_context import CommandContext
from xonsh.built_ins import XSH
import xonsh.lazyasd as xl

from xonsh.completers.tools import (
    get_filter_function,
    contextual_command_completer,
    sub_proc_get_output,
    RichCompletion,
)


@xl.lazyobject
def SCRAPE_RE():
    return re.compile(r"^(?:\s*(?:-\w|--[a-z0-9-]+)[\s,])+", re.M)


@xl.lazyobject
def INNER_OPTIONS_RE():
    return re.compile(r"-\w|--[a-z0-9-]+")


@functools.lru_cache
def get_man_completions_path() -> Path:
    env = XSH.env or {}
    datadir = Path(env["XONSH_DATA_DIR"]) / "man_completions_cache"
    if not datadir.exists():
        datadir.mkdir(exist_ok=True, parents=True)
    return datadir


def _get_man_page(cmd: str):
    """without control characters"""
    env = XSH.env.detype()
    manpage = subprocess.Popen(
        ["man", cmd], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env
    )
    # This is a trick to get rid of reverse line feeds
    return subprocess.check_output(["col", "-b"], stdin=manpage.stdout, env=env)


def generate_options_of(cmd: str):
    out = _get_man_page(cmd)
    if not out:
        return

    def get_headers(text: str):
        """split as header-body based on indent"""
        header = ""
        body = []
        for line in textwrap.dedent(text.replace("\n\t", "\n    ")).splitlines():
            if not line.strip():
                continue
            if line.startswith((" ", "\t")):
                body.append(line)
            else:
                if header or body:
                    yield header, body

                # found new section
                header = line.strip()
                body = []
        if header or body:
            yield header, body

    def get_opt_headers(text: str):
        for header, lines in get_headers(text):
            if header.lower() in {
                "description",
                "options",
                "command options",
            }:
                yield header, "\n".join(lines)

    def split_options_string(text: str):
        done_options = False
        options = []
        rest = []
        for part in text.split():
            if (not done_options) and part.startswith("-"):
                options.append(part.rstrip(","))
            else:
                done_options = True
                rest.append(part)
        return options, " ".join(rest)

    for _, body in get_opt_headers(out.decode()):
        # return old section if
        for opt, lines in get_headers(body):
            if opt.startswith("-"):
                # sometime a single line will have both desc and options
                option_strings, rest = split_options_string(opt)
                descs = []
                if rest:
                    descs.append(rest)
                if lines:
                    descs.append(textwrap.dedent("\n".join(lines)))

                yield "\n".join(descs), tuple(option_strings)


@functools.lru_cache(maxsize=10)
def get_options_of(cmd: str) -> "dict[str, tuple[str, ...]]":
    path = get_man_completions_path() / f"{cmd}.json"
    if path.exists():
        return json.loads(path.read_text())
    options = dict(generate_options_of(cmd))
    path.write_text(json.dumps(options))
    return options


@contextual_command_completer
def complete_from_man(context: CommandContext):
    """
    Completes an option name, based on the contents of the associated man
    page.
    """

    if context.arg_index == 0 or not context.prefix.startswith("-"):
        return
    cmd = context.args[0].value

    for desc, opts in get_options_of(cmd).items():
        yield RichCompletion(value=opts[-1], display=", ".join(opts), description=desc)
