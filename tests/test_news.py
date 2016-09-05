# -*- coding: utf-8 -*-
"""Testing that news entries are well formed."""
import os
import pytest

from xonsh.platform import scandir

NEWSDIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'news')

CATEGORIES = frozenset(['Added', 'Changed', 'Deprecated', 'Removed',
                        'Fixed', 'Security'])


def check_news_file(fname):
    with open(fname) as f:
        lines = f.read().splitlines()
    nlines = len(lines)
    for i, line in enumerate(lines):
        if line.startswith('**'):
            cat, *_ = line[2:].rsplit(':')
            assert cat in CATEGORIES
            if i+1 == nlines:
                continue
            assert lines[i+1].strip() == ''
            if line.endswith('None'):
                assert lines[i+2].startswith('**')
            else:
                assert lines[i+2].startswith('* ')
        else:
            starts_with_star_space = line.startswith('* ')
            assert (starts_with_star_space
                    or line.startswith('  ')
                    or (line.strip() == ''))
            if starts_with_star_space and '`' in line:
                pass



@pytest.mark.parametrize('fname', list(scandir(NEWSDIR)))
def test_news(fname):
    base, ext = os.path.splitext(fname.path)
    assert 'rst' in ext
    check_news_file(fname.path)
