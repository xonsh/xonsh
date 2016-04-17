# -*- coding: utf-8 -*-
"""Tests foreign shells."""
from __future__ import unicode_literals, print_function
import os
import subprocess

import nose
from nose.plugins.skip import SkipTest
from nose.tools import assert_equal, assert_true, assert_false

from xonsh.tools import ON_WINDOWS
from xonsh.foreign_shells import foreign_shell_data, parse_env, parse_aliases

def test_parse_env():
    exp = {'X': 'YES', 'Y': 'NO'}
    s = ('some garbage\n'
         '__XONSH_ENV_BEG__\n'
         'Y=NO\n'
         'X=YES\n'
         '__XONSH_ENV_END__\n'
         'more filth')
    obs = parse_env(s)
    assert_equal(exp, obs)


def test_parse_aliases():
    exp = {'x': ['yes', '-1'], 'y': ['echo', 'no']}
    s = ('some garbage\n'
         '__XONSH_ALIAS_BEG__\n'
         "alias x='yes -1'\n"
         "alias y='echo    no'\n"
         '__XONSH_ALIAS_END__\n'
         'more filth')
    obs = parse_aliases(s)
    assert_equal(exp, obs)


def test_foreign_bash_data():
    expenv = {"EMERALD": "SWORD", 'MIGHTY': 'WARRIOR'}
    expaliases = {
        'l': ['ls', '-CF'],
        'la': ['ls', '-A'],
        'll': ['ls', '-a', '-lF'],
        }
    rcfile = os.path.join(os.path.dirname(__file__), 'bashrc.sh')
    try:
        obsenv, obsaliases = foreign_shell_data('bash', currenv=(),
                                                extra_args=('--rcfile', rcfile),
                                                safe=False)
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise SkipTest
    for key, expval in expenv.items():
        yield assert_equal, expval, obsenv.get(key, False)
    for key, expval in expaliases.items():
        yield assert_equal, expval, obsaliases.get(key, False)


def test_foreign_cmd_data():
    if not ON_WINDOWS:
        raise SkipTest
    env = (('ENV_TO_BE_REMOVED','test'),)
    batchfile = os.path.join(os.path.dirname(__file__), 'batch.bat')
    source_cmd ='call "{}"\necho off'.format(batchfile)
    try:
        obsenv, _ = foreign_shell_data('cmd',prevcmd=source_cmd, 
                                        currenv=env,
                                        interactive =False,
                                        sourcer='call',envcmd='set',
                                        use_tmpfile=True,
                                        safe=False)
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise SkipTest
    
    assert_true('ENV_TO_BE_ADDED' in obsenv) 
    assert_true(obsenv['ENV_TO_BE_ADDED']=='Hallo world')
    assert_true('ENV_TO_BE_REMOVED' not in obsenv)


if __name__ == '__main__':
    nose.runmodule()
