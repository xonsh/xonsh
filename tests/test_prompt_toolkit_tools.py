"""Tests some tools function for prompt_toolkit integration."""
from __future__ import unicode_literals, print_function

import nose
from nose.tools import assert_equal

from xonsh.tools import FakeChar
from xonsh.tools import format_prompt_for_prompt_toolkit


def test_format_prompt_for_prompt_toolkit():
    cases = [
        ('root $ ', ['r', 'o', 'o', 't', ' ', '$', ' ']),
        ('\001\033[0;31m\002>>',
            [FakeChar('>', prefix='\001\033[0;31m\002'), '>']
        ),
        ('\001\033[0;31m\002>>\001\033[0m\002',
            [FakeChar('>', prefix='\001\033[0;31m\002'),
             FakeChar('>', suffix='\001\033[0m\002')]
        ),
        ('\001\033[0;31m\002>\001\033[0m\002',
            [FakeChar('>',
                      prefix='\001\033[0;31m\002',
                      suffix='\001\033[0m\002')
            ]
        ),
        ('\001\033[0;31m\002> $\001\033[0m\002',
            [FakeChar('>', prefix='\001\033[0;31m\002'),
             ' ',
             FakeChar('$', suffix='\001\033[0m\002')]
        ),
        ('\001\033[0;31m\002\001\033[0;32m\002$> \001\033[0m\002',
            [FakeChar('$', prefix='\001\033[0;31m\002\001\033[0;32m\002'),
             '>',
             FakeChar(' ', suffix='\001\033[0m\002')]
        ),
        ]
    for test, ans in cases:
        yield assert_equal, ''.join(ans), format_prompt_for_prompt_toolkit(test)


if __name__ == '__main__':
    nose.runmodule()
