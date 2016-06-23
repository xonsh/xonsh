# -*- coding: utf-8 -*-
"""Testing built_ins.Aliases"""
from __future__ import unicode_literals, print_function

import os
import tempfile

import pytest

import xonsh.built_ins as built_ins
from xonsh.aliases import Aliases
from xonsh.aliases import _which
from xonsh.environ import Env
from xonsh.tools import ON_WINDOWS

from tools import mock_xonsh_env


def cd(args, stdin=None):
    return args

ALIASES = Aliases({'o': ['omg', 'lala']},
                  color_ls=['ls', '--color=true'],
                  ls="ls '-  -'",
                  cd=cd,
                  indirect_cd='cd ..')
RAW = ALIASES._raw

def test_imports():
    expected = {
        'o': ['omg', 'lala'],
        'ls': ['ls', '-  -'],
        'color_ls': ['ls', '--color=true'],
        'cd': cd,
        'indirect_cd': ['cd', '..']
    }
    assert RAW == expected

def test_eval_normal():
    with mock_xonsh_env({}):
        assert ALIASES.get('o') ==  ['omg', 'lala']

def test_eval_self_reference():
    with mock_xonsh_env({}):
        assert ALIASES.get('ls') ==  ['ls', '-  -']

def test_eval_recursive():
    with mock_xonsh_env({}):
        assert ALIASES.get('color_ls') ==  ['ls', '-  -', '--color=true']

@pytest.mark.skipif(ON_WINDOWS, reason='Unix stuff')
def test_eval_recursive_callable_partial():
    built_ins.ENV = Env(HOME=os.path.expanduser('~'))
    with mock_xonsh_env(built_ins.ENV):
        assert ALIASES.get('indirect_cd')(['arg2', 'arg3']) == ['..', 'arg2', 'arg3']

class TestWhich:
    # Tests for the _whichgen function which is the only thing we
    # use from the _which.py module.
    def setup(self):
        # Setup two folders with some test files.
        self.testdirs = [tempfile.TemporaryDirectory(),
                         tempfile.TemporaryDirectory()]
        if ON_WINDOWS:
            self.testapps = ['whichtestapp1.exe',
                             'whichtestapp2.wta']
            self.exts = ['.EXE']
        else:
            self.testapps = ['whichtestapp1']
            self.exts = None
        for app in self.testapps:
            for d in self.testdirs:
                path = os.path.join(d.name, app)
                open(path, 'wb').write(b'')
                os.chmod(path, 0o755)

    def teardown_module(self):
        for d in self.testdirs:
            d.cleanup()

    def test_whichgen(self):
        testdir = self.testdirs[0].name
        arg = 'whichtestapp1'
        matches = list(_which.whichgen(arg, path=[testdir], exts=self.exts))
        assert len(matches) == 1
        assert self._file_match(matches[0][0], os.path.join(testdir, arg))

    def test_whichgen_failure(self):
        testdir = self.testdirs[0].name
        arg = 'not_a_file'
        matches = list(_which.whichgen(arg, path=[testdir], exts=self.exts))
        assert len(matches) == 0

    def test_whichgen_verbose(self):
        testdir = self.testdirs[0].name
        arg = 'whichtestapp1'
        matches = list(_which.whichgen(arg, path=[testdir], exts=self.exts,
                                       verbose=True))
        assert len(matches) == 1
        match, from_where = matches[0]
        assert self._file_match(match, os.path.join(testdir, arg))
        assert from_where == 'from given path element 0'

    def test_whichgen_multiple(self):
        testdir0 = self.testdirs[0].name
        testdir1 = self.testdirs[1].name
        arg = 'whichtestapp1'
        matches = list(_which.whichgen(arg, path=[testdir0, testdir1],
                                       exts=self.exts))
        assert len(matches) == 2
        assert self._file_match(matches[0][0], os.path.join(testdir0, arg))
        assert self._file_match(matches[1][0], os.path.join(testdir1, arg))

    if ON_WINDOWS:
        def test_whichgen_ext_failure(self):
            testdir = self.testdirs[0].name
            arg = 'whichtestapp2'
            matches = list(_which.whichgen(arg, path=[testdir], exts=self.exts))
            assert len(matches) == 0

        def test_whichgen_ext_success(self):
                testdir = self.testdirs[0].name
                arg = 'whichtestapp2'
                matches = list(_which.whichgen(arg, path=[testdir], exts=['.wta']))
                assert len(matches) == 1
                assert self._file_match(matches[0][0], os.path.join(testdir, arg))

    def _file_match(self, path1, path2):
        if ON_WINDOWS:
            path1 = os.path.normpath(os.path.normcase(path1))
            path2 = os.path.normpath(os.path.normcase(path2))
            path1 = os.path.splitext(path1)[0]
            path2 = os.path.splitext(path2)[0]
            return path1 == path2
        else:
            return os.path.samefile(path1, path2)
