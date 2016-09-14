# -*- coding: utf-8 -*-
"""Testing that news entries are well formed."""
import os
import re

import pytest

from xonsh.platform import scandir


NEWSDIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'news')

CATEGORIES = frozenset(['Added', 'Changed', 'Deprecated', 'Removed',
                        'Fixed', 'Security'])

single_grave_reg = re.compile(r'[^`]`[^`]+`[^`_]')

def check_news_file(fname):
    name = fname.name
    with open(fname.path) as f:
        lines = f.read().splitlines()
    nlines = len(lines)
    for i, line in enumerate(lines):
        if line.startswith('**'):
            cat, *_ = line[2:].rsplit(':')
            if cat not in CATEGORIES:
                pytest.fail('{}:{}: {!r} not a proper category '
                            'must be one of {}'
                            ''.format(name, i+1, cat, list(CATEGORIES)),
                            pytrace=False)
            if i+1 == nlines:
                continue
            if not lines[i+1].strip() == '':
                pytest.fail('{}:{}: empty line required after category'
                            ''.format(name, i+1), pytrace=False)
            if i > 0 and not lines[i-1].strip() == '':
                pytest.fail('{}:{}: empty line required before category'
                            ''.format(name, i+1), pytrace=False)
            if line.endswith('None'):
                if not lines[i+2].startswith('**'):
                    pytest.fail("{}:{}: can't have entries after None"
                                ''.format(name, i+1), pytrace=False)
            else:
                if lines[i+2].startswith('**'):
                    pytest.fail("{}:{}: must have entry if not None"
                                ''.format(name, i+1), pytrace=False)
        else:
            if not (line.startswith('* ')
                    or line.startswith('  ')
                    or (line.strip() == '')):
                pytest.fail('{}:{}: invalid rst'.format(name, i+1),
                            pytrace=False)
            if '`' in line:
                if single_grave_reg.search(line):
                    pytest.fail("{}:{}: single grave accents"
                                " are not valid rst".format(name, i+1),
                                pytrace=False)


@pytest.mark.parametrize('fname', list(scandir(NEWSDIR)))
def test_news(fname):
    base, ext = os.path.splitext(fname.path)
    assert 'rst' in ext
    check_news_file(fname)
