"""Prompt formatter for virtualenv and others"""

import re
from pathlib import Path

from xonsh.built_ins import XSH


def env_name():
    """Build env_name based on different sources. Respect order of precedence.

    Name from VIRTUAL_ENV_PROMPT will be used as-is.
    Names from other sources are surrounded with ``{env_prefix}`` and
    ``{env_postfix}`` fields.
    """
    if XSH.env.get("VIRTUAL_ENV_DISABLE_PROMPT"):
        return
    virtual_env_prompt = XSH.env.get("VIRTUAL_ENV_PROMPT")
    if virtual_env_prompt:
        return virtual_env_prompt
    virtual_env = XSH.env.get("VIRTUAL_ENV")
    if virtual_env:
        venv_path = Path(virtual_env)
        pyvenv_cfg_prompt = prompt_from_pyvenv_cfg(venv_path)
        if pyvenv_cfg_prompt:
            return surround_env_name(pyvenv_cfg_prompt)
        return surround_env_name(venv_path.name)
    from_conda = XSH.env.get("CONDA_DEFAULT_ENV")
    if from_conda:
        return surround_env_name(from_conda)
    return


def prompt_from_pyvenv_cfg(venv_path):
    """Grab the prompt from the venv configuration, if it exists.

    Tries to be resilient to subtle changes in whitespace and quoting in the
    configuration file format as it adheres to no clear standard.
    """
    assert isinstance(venv_path, Path), venv_path
    pyvenv_cfg = venv_path / "pyvenv.cfg"
    if pyvenv_cfg.is_file():
        match = re.search(r"prompt\s*=\s*(.*)", pyvenv_cfg.read_text())
        if match:
            return match.group(1).strip().lstrip("'\"").rstrip("'\"")


def surround_env_name(name):
    pf = XSH.shell.prompt_formatter
    pre = pf._get_field_value("env_prefix")
    post = pf._get_field_value("env_postfix")
    return f"{pre}{name}{post}"


def vte_new_tab_cwd():
    """This prints an escape sequence that tells VTE terminals the hostname
    and pwd. This should not be needed in most cases, but sometimes is for
    certain Linux terminals that do not read the PWD from the environment
    on startup. Note that this does not return a string, it simply prints
    and flushes the escape sequence to stdout directly.
    """
    env = XSH.env
    t = "\033]7;file://{}{}\007"
    s = t.format(env.get("HOSTNAME"), env.get("PWD"))
    print(s, end="", flush=True)
