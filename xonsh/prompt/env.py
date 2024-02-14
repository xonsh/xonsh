"""Prompt formatter for virtualenv and others"""

import functools
import re
from pathlib import Path
from typing import Optional

from xonsh.built_ins import XSH


def find_env_name() -> Optional[str]:
    """Find current environment name from available sources.

    If ``$VIRTUAL_ENV`` is set, it is determined from the prompt setting in
    ``<venv>/pyvenv.cfg`` or from the folder name of the environment.

    Otherwise - if it is set - from ``$CONDA_DEFAULT_ENV``.
    """
    virtual_env = XSH.env.get("VIRTUAL_ENV")
    if virtual_env:
        name = _determine_env_name(virtual_env)
        if name:
            return name
    conda_default_env = XSH.env.get("CONDA_DEFAULT_ENV")
    if conda_default_env:
        return conda_default_env


def env_name() -> str:
    """Build env_name based on different sources. Respect order of precedence.

    Name from VIRTUAL_ENV_PROMPT will be used as-is.
    Names from other sources are surrounded with ``{env_prefix}`` and
    ``{env_postfix}`` fields.
    """
    if XSH.env.get("VIRTUAL_ENV_DISABLE_PROMPT"):
        return ""
    virtual_env_prompt = XSH.env.get("VIRTUAL_ENV_PROMPT")
    if virtual_env_prompt:
        return virtual_env_prompt
    found_envname = find_env_name()
    return _surround_env_name(found_envname) if found_envname else ""


@functools.lru_cache(maxsize=5)
def _determine_env_name(virtual_env: str) -> str:
    """Use prompt setting from pyvenv.cfg or basename of virtual_env.

    Tries to be resilient to subtle changes in whitespace and quoting in the
    configuration file format as it adheres to no clear standard.
    """
    venv_path = Path(virtual_env)
    pyvenv_cfg = venv_path / "pyvenv.cfg"
    if pyvenv_cfg.is_file():
        match = re.search(r"prompt\s*=\s*(.*)", pyvenv_cfg.read_text())
        if match:
            return match.group(1).strip().lstrip("'\"").rstrip("'\"")
    return venv_path.name


def _surround_env_name(name: str) -> str:
    pf = XSH.shell.prompt_formatter
    pre = pf._get_field_value("env_prefix")
    post = pf._get_field_value("env_postfix")
    return f"{pre}{name}{post}"


def vte_new_tab_cwd() -> None:
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
