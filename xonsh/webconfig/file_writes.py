"""functions to update rc files"""
import os
import typing as tp

RENDERERS: tp.List[tp.Callable] = []


def renderer(f):
    """Adds decorated function to renderers list."""
    RENDERERS.append(f)


@renderer
def prompt(config):
    prompt = config.get("prompt")
    if prompt:
        yield f"$PROMPT = {prompt!r}"


@renderer
def colors(config):
    style = config.get("color")
    if style:
        yield f"$XONSH_COLOR_STYLE = {style!r}"


@renderer
def xontribs(config):
    xtribs = config.get("xontribs")
    if xtribs:
        yield "xontrib load " + " ".join(xtribs)


def config_to_xonsh(
    config, prefix="# XONSH WEBCONFIG START", suffix="# XONSH WEBCONFIG END"
):
    """Turns config dict into xonsh code (str)."""
    lines = [prefix]
    for func in RENDERERS:
        lines.extend(func(config))
    lines.append(suffix)
    return "\n".join(lines)


def insert_into_xonshrc(
    config,
    xonshrc="~/.xonshrc",
    prefix="# XONSH WEBCONFIG START",
    suffix="# XONSH WEBCONFIG END",
):
    """Places a config dict into the xonshrc."""
    # get current contents
    fname = os.path.expanduser(xonshrc)
    if os.path.isfile(fname):
        with open(fname) as f:
            s = f.read()
        before, _, s = s.partition(prefix)
        _, _, after = s.partition(suffix)
    else:
        before = after = ""
        dname = os.path.dirname(fname)
        if dname:
            os.makedirs(dname, exist_ok=True)
    # compute new values
    new = config_to_xonsh(config, prefix=prefix, suffix=suffix)
    # write out the file
    with open(fname, "w", encoding="utf-8") as f:
        f.write(before + new + after)
    return fname
