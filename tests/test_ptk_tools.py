# -*- coding: utf-8 -*-
"""Tests some tools function for prompt_toolkit integration."""
from __future__ import unicode_literals, print_function

import nose
from nose.tools import assert_equal

import builtins
from xonsh.tools import format_prompt_for_prompt_toolkit
from xonsh.tools import TERM_COLORS
from xonsh.environ import format_prompt, Env

builtins.__xonsh_env__ = Env()
builtins.__xonsh_env__['PROMPT_TOOLKIT_COLORS'] = {'WHITE': '#ffffff'}

def test_format_prompt_for_prompt_toolkit():
    templ = ('>>> {BOLD_BLUE}~/xonsh {WHITE} (main){NO_COLOR}')
    prompt = format_prompt(templ, TERM_COLORS)
    token_names, color_styles, strings = format_prompt_for_prompt_toolkit(prompt)
    assert_equal(token_names, ['NO_COLOR', 'BOLD_BLUE', 'WHITE', 'NO_COLOR'])
    assert_equal(color_styles, ['', 'bold #0000D2', '#ffffff', ''])
    assert_equal(strings, ['>>> ', '~/xonsh ', ' (main)', ''])


if __name__ == '__main__':
    nose.runmodule()
