# -*- coding: utf-8 -*-
"""Testing that news entries are well formed."""
import os

from xonsh.platform import scandir

CATEGORIES = frozenset(['Added', 'Changed', 'Deprecated', 'Removed',
                        'Fixed', 'Security'])


def check_news_file(fname):
    with open(fname) as f:
        lines = f.read().splitlines()
    nlines = len(lines)
    for i, line in enumerate(lines):
        if line.startswith('**'):
            cat, _, _ = line[2:].partition(':')
            assert cat in CATEGORIES
            if i+1 == nlines:
                continue
            assert lines[i+1].strip() == ''
            if line.endswith('None'):
                assert lines[i+2].startswith('**')
            else:
                assert lines[i+2].startswith('* ')
        else:
            assert line.startswith('* ') or line.startswith('  ') or \
                   (line.strip() == '')


def test_news():
    newsdir = os.path.join(os.path.dirname(
                           os.path.dirname(__file__)), 'news')
    for f in scandir(newsdir):
        base, ext = os.path.splitext(f.path)
        assert 'rst' in ext
        yield check_news_file, f.path
