# -*- coding: utf-8 -*-
"""Base prompt, provides FORMATTER_DICT and prompt related functions"""

import builtins
import itertools
import os
import re
import socket
import string
import sys

import xonsh.lazyasd as xl
import xonsh.tools as xt
import xonsh.platform as xp

from xonsh.prompt.cwd import (
    _collapsed_pwd, _replace_home_cwd, _dynamically_collapsed_pwd
)
from xonsh.prompt.job import _current_job
from xonsh.prompt.env import (env_name, vte_new_tab_cwd)
from xonsh.prompt.vc_branch import (
    current_branch, branch_color, branch_bg_color
)
from xonsh.prompt.gitstatus import gitstatus_prompt


@xl.lazyobject
def FORMATTER_DICT():
    return dict(
        user=os.environ.get('USERNAME' if xp.ON_WINDOWS else 'USER', '<user>'),
        prompt_end='#' if xt.is_superuser() else '$',
        hostname=socket.gethostname().split('.', 1)[0],
        cwd=_dynamically_collapsed_pwd,
        cwd_dir=lambda: os.path.dirname(_replace_home_cwd()),
        cwd_base=lambda: os.path.basename(_replace_home_cwd()),
        short_cwd=_collapsed_pwd,
        curr_branch=current_branch,
        branch_color=branch_color,
        branch_bg_color=branch_bg_color,
        current_job=_current_job,
        env_name=env_name,
        vte_new_tab_cwd=vte_new_tab_cwd,
        gitstatus=gitstatus_prompt,
    )


@xl.lazyobject
def _FORMATTER():
    return string.Formatter()


def default_prompt():
    """Creates a new instance of the default prompt."""
    if xp.ON_CYGWIN:
        dp = ('{env_name:{} }{BOLD_GREEN}{user}@{hostname}'
              '{BOLD_BLUE} {cwd} {prompt_end}{NO_COLOR} ')
    elif xp.ON_WINDOWS:
        dp = ('{env_name:{} }'
              '{BOLD_INTENSE_GREEN}{user}@{hostname}{BOLD_INTENSE_CYAN} '
              '{cwd}{branch_color}{curr_branch: {}}{NO_COLOR} '
              '{BOLD_INTENSE_CYAN}{prompt_end}{NO_COLOR} ')
    else:
        dp = ('{env_name:{} }'
              '{BOLD_GREEN}{user}@{hostname}{BOLD_BLUE} '
              '{cwd}{branch_color}{curr_branch: {}}{NO_COLOR} '
              '{BOLD_BLUE}{prompt_end}{NO_COLOR} ')
    return dp


@xt.lazyobject
def DEFAULT_PROMPT():
    return default_prompt()


def _get_fmtter(formatter_dict=None):
    if formatter_dict is None:
        fmtter = builtins.__xonsh_env__.get('FORMATTER_DICT', FORMATTER_DICT)
    else:
        fmtter = formatter_dict
    return fmtter


def _failover_template_format(template):
    if callable(template):
        try:
            # Exceptions raises from function of producing $PROMPT
            # in user's xonshrc should not crash xonsh
            return template()
        except Exception:
            xt.print_exception()
            return '$ '
    return template


def partial_format_prompt(template=DEFAULT_PROMPT, formatter_dict=None):
    """Formats a xonsh prompt template string."""
    try:
        return _partial_format_prompt_main(template=template,
                                           formatter_dict=formatter_dict)
    except Exception:
        return _failover_template_format(template)


def _partial_format_prompt_main(template=DEFAULT_PROMPT, formatter_dict=None):
    template = template() if callable(template) else template
    fmtter = _get_fmtter(formatter_dict)
    bopen = '{'
    bclose = '}'
    colon = ':'
    expl = '!'
    toks = []
    for literal, field, spec, conv in _FORMATTER.parse(template):
        toks.append(literal)
        if field is None:
            continue
        elif field.startswith('$'):
            val = builtins.__xonsh_env__[field[1:]]
            val = _format_value(val, spec, conv)
            toks.append(val)
        elif field in fmtter:
            v = fmtter[field]
            try:
                val = v() if callable(v) else v
            except Exception as err:
                print('prompt: error: on field {!r}'
                      ''.format(field), file=sys.stderr)
                xt.print_exception()
                toks.append('(ERROR:{})'.format(field))
                continue
            val = _format_value(val, spec, conv)
            toks.append(val)
        else:
            toks.append(bopen)
            toks.append(field)
            if conv is not None and len(conv) > 0:
                toks.append(expl)
                toks.append(conv)
            if spec is not None and len(spec) > 0:
                toks.append(colon)
                toks.append(spec)
            toks.append(bclose)
    return ''.join(toks)


@xt.lazyobject
def RE_HIDDEN():
    return re.compile('\001.*?\002')


def multiline_prompt(curr=''):
    """Returns the filler text for the prompt in multiline scenarios."""
    line = curr.rsplit('\n', 1)[1] if '\n' in curr else curr
    line = RE_HIDDEN.sub('', line)  # gets rid of colors
    # most prompts end in whitespace, head is the part before that.
    head = line.rstrip()
    headlen = len(head)
    # tail is the trailing whitespace
    tail = line if headlen == 0 else line.rsplit(head[-1], 1)[1]
    # now to constuct the actual string
    dots = builtins.__xonsh_env__.get('MULTILINE_PROMPT')
    dots = dots() if callable(dots) else dots
    if dots is None or len(dots) == 0:
        return ''
    tokstr = xt.format_color(dots, hide=True)
    baselen = 0
    basetoks = []
    for x in tokstr.split('\001'):
        pre, sep, post = x.partition('\002')
        if len(sep) == 0:
            basetoks.append(('', pre))
            baselen += len(pre)
        else:
            basetoks.append(('\001' + pre + '\002', post))
            baselen += len(post)
    if baselen == 0:
        return xt.format_color('{NO_COLOR}' + tail, hide=True)
    toks = basetoks * (headlen // baselen)
    n = headlen % baselen
    count = 0
    for tok in basetoks:
        slen = len(tok[1])
        newcount = slen + count
        if slen == 0:
            continue
        elif newcount <= n:
            toks.append(tok)
        else:
            toks.append((tok[0], tok[1][:n - count]))
        count = newcount
        if n <= count:
            break
    toks.append((xt.format_color('{NO_COLOR}', hide=True), tail))
    rtn = ''.join(itertools.chain.from_iterable(toks))
    return rtn


def is_template_string(template, formatter_dict=None):
    """Returns whether or not the string is a valid template."""
    template = template() if callable(template) else template
    try:
        included_names = set(i[1] for i in _FORMATTER.parse(template))
    except ValueError:
        return False
    included_names.discard(None)
    if formatter_dict is None:
        fmtter = builtins.__xonsh_env__.get('FORMATTER_DICT', FORMATTER_DICT)
    else:
        fmtter = formatter_dict
    known_names = set(fmtter.keys())
    return included_names <= known_names


def _format_value(val, spec, conv):
    """Formats a value from a template string {val!conv:spec}. The spec is
    applied as a format string itself, but if the value is None, the result
    will be empty. The purpose of this is to allow optional parts in a
    prompt string. For example, if the prompt contains '{current_job:{} | }',
    and 'current_job' returns 'sleep', the result is 'sleep | ', and if
    'current_job' returns None, the result is ''.
    """
    if val is None:
        return ''
    val = _FORMATTER.convert_field(val, conv)
    if spec:
        val = _FORMATTER.format(spec, val)
    if not isinstance(val, str):
        val = str(val)
    return val
