"""Tests the xonsh Prompt Formatter."""
from __future__ import unicode_literals, print_function

import os
import sys
import time
import socket
from datetime import datetime, timedelta
from unittest import mock

sys.path.insert(0, os.path.abspath('..'))  # FIXME

import nose
from nose.tools import eq_, ok_, assert_in, assert_is_instance
from nose.plugins.skip import SkipTest

from .tools import mock_xonsh_env
from xonsh.tools import TERM_COLORS

from xonsh.environ import PromptFormatter, DefaultPromptFormatter


class TestPromptFormatter:
    """ Test that the basics of getting static, callonce, and callevery values works """

    def call_once_func(self):
        self.call_once_counter += 1
        return self.call_once_counter

    def call_every_func(self):
        self.call_every_counter += 1
        return self.call_every_counter

    def setUp(self):
        self.call_once_counter = 0
        self.call_every_counter = 0

        self.base_formatter = PromptFormatter()
        self.base_formatter['var'] = 'value'
        self.base_formatter['callonce'] = self.call_once_func
        self.base_formatter['callevery'] = self.call_every_func
        self.base_formatter._run_every.add('callevery')

    def test_get_items_static(self):
        eq_(self.base_formatter['var'], 'value')
        eq_(self.base_formatter['var'], 'value')

    def test_get_items_callonce(self):
        eq_(self.base_formatter['callonce'], 1)
        eq_(self.base_formatter['callonce'], 1)

    def test_get_items_callevery(self):
        eq_(self.base_formatter['callevery'], 1)
        eq_(self.base_formatter['callevery'], 2)

    def check_splat(self, **kwargs):
        assert_is_instance(kwargs, dict)
        eq_(len(kwargs), 3)

        assert_in('var', kwargs)
        assert_in('callonce', kwargs)
        assert_in('callevery', kwargs)

        eq_(kwargs['var'], 'value')
        eq_(kwargs['callonce'], 1)
        # Repeat this to prove it's not a function being called anymore
        eq_(kwargs['callevery'], 1)
        eq_(kwargs['callevery'], 1)

    def test_splat(self):
        self.check_splat(**self.base_formatter)

class TestDefaultPromptFormatter:
    """Test each of the prompt variables that DefaultPromptFormatter adds"""

    def setUp(self):
        self.color_names = frozenset(TERM_COLORS.keys())
        self.dynamic_names = frozenset(['base_cwd',
                                        'cwd',
                                        'curr_branch',
                                        'hostname',
                                        'short_host',
                                        'time',
                                        'user'])
        self.all_names = self.color_names.union(self.dynamic_names)
        self.env = dict(PWD='/home/xonsh', USER='xonshuser', HOME='/home/xonsh')
        with mock_xonsh_env(self.env):
            self.default_formatter = DefaultPromptFormatter()

    def test_get_color(self):
        with mock_xonsh_env(self.env):
            format_vars = frozenset(self.default_formatter.keys())
            ok_(self.color_names.issubset(format_vars))

            assert_in('YELLOW', TERM_COLORS)
            assert_in('YELLOW', self.default_formatter)

            eq_(TERM_COLORS['YELLOW'], self.default_formatter['YELLOW'])

    def test_get_base_cwd(self):
        with mock_xonsh_env(self.env):
            import builtins
            eq_('~', self.default_formatter['base_cwd'])
            builtins.__xonsh_env__['PWD'] = '/home/xonsh/public_html'
            eq_('public_html', self.default_formatter['base_cwd'])
            builtins.__xonsh_env__['PWD'] = '/var/tmp'
            eq_('tmp', self.default_formatter['base_cwd'])

    def test_get_cwd(self):
        with mock_xonsh_env(self.env):
            import builtins
            eq_('~', self.default_formatter['cwd'])
            builtins.__xonsh_env__['PWD'] = '/home/xonsh/public_html'
            eq_('~/public_html', self.default_formatter['cwd'])
            builtins.__xonsh_env__['PWD'] = '/var/tmp'
            eq_('/var/tmp', self.default_formatter['cwd'])

    def test_curr_branch(self):
        raise SkipTest('Testing of git branch detection not implemented')
        with mock_xonsh_env(self.env):
            ### TODO: need to test that git branch detection works.
            # If not in a git repository, return ''
            # If in a git repository, return the branch name
            pass

    def test_hostname(self):
        with mock_xonsh_env(self.env):
            # Not a great test -- hostname is just calling socket.getfqdn so
            # this is doesn't test much
            eq_(socket.getfqdn(), self.default_formatter['hostname'])

    def test_short_host_fqdn(self):
        with mock_xonsh_env(self.env):
            # Not a great test default_formatter is such a light wrapper
            # around socket.gethostname that this doesn't really test much
            with mock.patch('socket.gethostname', new=lambda : 'www.example.com'):
                eq_('www', self.default_formatter['short_host'])

    def test_short_host_short(self):
        with mock_xonsh_env(self.env):
            # Not a great test default_formatter is such a light wrapper
            # around socket.gethostname that this doesn't really test much
            with mock.patch('socket.gethostname', new=lambda : 'localhost'):
                eq_('localhost', self.default_formatter['short_host'])

    def test_get_time(self):
        with mock_xonsh_env(self.env):
            now = datetime.now()
            format_reported = self.default_formatter['time']
            ok_(format_reported - now < timedelta(0, 1))
            time.sleep(2)
            now2 = datetime.now()
            ok_(now2 - now > timedelta(0, 2))
            format_reported = self.default_formatter['time']
            ok_(format_reported - now2 < timedelta(0, 1))

    def test_get_user(self):
        with mock_xonsh_env(self.env):
            eq_('xonshuser', self.default_formatter['user'])

    def check_splat(self, **kwargs):
        assert_is_instance(kwargs, dict)
        eq_(len(TERM_COLORS) + 7, len(kwargs))
        kwarg_vars = frozenset(kwargs.keys())
        eq_(self.all_names, kwarg_vars)

    def test_splat(self):
        with mock_xonsh_env(self.env):
            self.check_splat(**self.default_formatter)

    def test_format(self):
        with mock_xonsh_env(self.env):
            for name in (n for n in self.all_names if n != 'time'):
                fstring = r'{%s}' % name
                eq_(fstring.format(**self.default_formatter), self.default_formatter[name])

            now = datetime.now()
            fstring = r'{time:%Y-%m-%d %H:%M:%S}'.format(**self.default_formatter)
            ok_(datetime.strptime(fstring, '%Y-%m-%d %H:%M:%S') - now < timedelta(0, 2))
