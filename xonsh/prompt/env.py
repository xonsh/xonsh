# -*- coding: utf-8 -*-
"""Prompt formatter for virtualenv and others"""

import os
import builtins

import xonsh.platform as xp


def find_env_name():
    """Finds the current environment name from $VIRTUAL_ENV or
    $CONDA_DEFAULT_ENV if that is set.
    """
    env_path = builtins.__xonsh__.env.get("VIRTUAL_ENV", "")
    if len(env_path) == 0 and xp.ON_ANACONDA:
        env_path = builtins.__xonsh__.env.get("CONDA_DEFAULT_ENV", "")
    env_name = os.path.basename(env_path)
    return env_name


def env_name():
    """Returns the current env_name if it non-empty, surrounded by the
    ``{env_prefix}`` and ``{env_postfix}`` fields.
    """
    env_name = find_env_name()
    if builtins.__xonsh__.env.get("VIRTUAL_ENV_DISABLE_PROMPT") or not env_name:
        # env name prompt printing disabled, or no environment; just return
        return

    venv_prompt = builtins.__xonsh__.env.get("VIRTUAL_ENV_PROMPT")
    if venv_prompt is not None:
        return venv_prompt
    else:
        pf = builtins.__xonsh__.shell.prompt_formatter
        pre = pf._get_field_value("env_prefix")
        post = pf._get_field_value("env_postfix")
        return pre + env_name + post


def vte_new_tab_cwd():
    """This prints an escape sequence that tells VTE terminals the hostname
    and pwd. This should not be needed in most cases, but sometimes is for
    certain Linux terminals that do not read the PWD from the environment
    on startup. Note that this does not return a string, it simply prints
    and flushes the escape sequence to stdout directly.
    """
    env = builtins.__xonsh__.env
    t = "\033]7;file://{}{}\007"
    s = t.format(env.get("HOSTNAME"), env.get("PWD"))
    print(s, end="", flush=True)
