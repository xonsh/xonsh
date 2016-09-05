# -*- coding: utf-8 -*-
"""Prompt formatter for virtualenv and others"""

import os
import builtins

import xonsh.platform as xp


def env_name(pre_chars='(', post_chars=')'):
    """Extract the current environment name from $VIRTUAL_ENV or
    $CONDA_DEFAULT_ENV if that is set
    """
    env_path = builtins.__xonsh_env__.get('VIRTUAL_ENV', '')
    if len(env_path) == 0 and xp.ON_ANACONDA:
        env_path = builtins.__xonsh_env__.get('CONDA_DEFAULT_ENV', '')
    env_name = os.path.basename(env_path)
    if env_name:
        return pre_chars + env_name + post_chars


def vte_new_tab_cwd():
    """This prints an escape squence that tells VTE terminals the hostname
    and pwd. This should not be needed in most cases, but sometimes is for
    certain Linux terminals that do not read the PWD from the environment
    on startup. Note that this does not return a string, it simply prints
    and flushes the escape sequence to stdout directly.
    """
    env = builtins.__xonsh_env__
    t = '\033]7;file://{}{}\007'
    s = t.format(env.get('HOSTNAME'), env.get('PWD'))
    print(s, end='', flush=True)
