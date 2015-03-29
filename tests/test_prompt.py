"""Tests the xonsh Prompt Formatter."""
from __future__ import unicode_literals, print_function

import os
import sys
import copy
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

from xonsh.environ import (PromptFormatter, DefaultPromptFormatter,
        DEFAULT_PROMPT, DEFAULT_TITLE, add_prompt_var)


class Base_TestPromptFormatter:
    def call_once_func(self):
        self.call_once_counter += 1
        return self.call_once_counter

    def call_every_func(self):
        self.call_every_counter += 1
        return self.call_every_counter

    def setUp(self):
        self.base_formatter = PromptFormatter('No vars to substitute')
        self.call_once_counter = 0
        self.call_every_counter = 0

    def check_get_var(self, var_name, expected):
        eq_(self.base_formatter[var_name], expected)


class TestAddPromptVar(Base_TestPromptFormatter):
    def test_add_string_no_call(self):
        self.base_formatter.add_prompt_var('var1', 'value1', call_every=True)
        self.check_get_var('var1', 'value1')
        self.check_get_var('var1', 'value1')

    def test_add_string_with_call(self):
        """ Test that we gracefully handle the case where var is a string and call_every is True"""
        self.base_formatter.add_prompt_var('var2', 'value2', call_every=False)
        self.check_get_var('var2', 'value2')
        self.check_get_var('var2', 'value2')

    def test_add_call_once_func(self):
        self.base_formatter.add_prompt_var('callonce', self.call_once_func, call_every=False)
        self.check_get_var('callonce', 1)
        self.check_get_var('callonce', 1)

    def test_add_call_every_func(self):
        self.base_formatter.add_prompt_var('callevery', self.call_every_func, call_every=True)
        self.check_get_var('callevery', 1)
        self.check_get_var('callevery', 2)


class TestPromptFormatter(Base_TestPromptFormatter):
    """ Test that the basics of getting static, callonce, and callevery values works """

    def setUp(self):
        super(TestPromptFormatter, self).setUp()
        self.base_formatter['var'] = 'value'
        self.base_formatter['callonce'] = self.call_once_func
        self.base_formatter['callevery'] = self.call_every_func
        self.base_formatter._run_every.add('callevery')

    def test_get_items_static(self):
        self.check_get_var('var', 'value')
        self.check_get_var('var', 'value')

    def test_get_items_callonce(self):
        self.check_get_var('callonce', 1)
        self.check_get_var('callonce', 1)

    def test_get_items_callevery(self):
        self.check_get_var('callevery', 1)
        self.check_get_var('callevery', 2)

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
            self.default_formatter = DefaultPromptFormatter('No vars to substitute')

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

#
# Behaviour Tests
#

class TestPromptFormatterBehaviour:

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
            self.default_formatter = DefaultPromptFormatter('No prompt vars to substitute')

    def test_individual_formats(self):
        """Test each of the prompt variables that DefaultPromptFormatter adds"""
        with mock_xonsh_env(self.env):
            for name in (n for n in self.all_names if n != 'time'):
                self.default_formatter.prompt_string = r'{%s}' % name
                eq_(self.default_formatter(), self.default_formatter[name])

            now = datetime.now()
            self.default_formatter.prompt_string = r'{time:%Y-%m-%d %H:%M:%S}'
            ok_(datetime.strptime(self.default_formatter(), '%Y-%m-%d %H:%M:%S') - now < timedelta(0, 2))

    def test_default_prompt(self):
        """Test that default prompt string expands

        Mainly interested in this not throwing an exception because some
        prompt vars in the default prompt do not have a corresponding
        implementation in the DefaultPromptFormatter Will detect a few other
        errors as well but it's not intended to be complete about those.
        """
        with mock_xonsh_env(self.env):
            prompt_start = '{}xonshuser@{}{} ~{}'.format(
                                                    TERM_COLORS['BOLD_GREEN'],
                                                    socket.getfqdn(),
                                                    TERM_COLORS['BOLD_BLUE'],
                                                    TERM_COLORS['BOLD_RED'])
            prompt_end = ' {}${} '.format(TERM_COLORS['BOLD_BLUE'],
                                          TERM_COLORS['NO_COLOR'])

            # Not sure how to test the git branch -- our test environment
            # could be run in a git clone or outside of a git clone and inside
            # or outside of an arbitrary branch.  So just check the beginning
            # and end.
            self.default_formatter.prompt_string = DEFAULT_PROMPT
            ok_(self.default_formatter().startswith(prompt_start))
            ok_(self.default_formatter().endswith(prompt_end))

    def test_default_title(self):
        """Test that default title string expands

        Mainly interested in this not throwing an exception because some
        prompt vars in the default title do not have a corresponding
        implementation in the DefaultPromptFormatter Will detect a few other
        errors as well but it's not intended to be complete about those.
        """
        with mock_xonsh_env(self.env):
            prompt = 'xonshuser@{}: ~ | xonsh'.format(socket.getfqdn())
            self.default_formatter.prompt_string = DEFAULT_TITLE
            eq_(self.default_formatter(), prompt)

    def test_custom_prompt_formatter(self):

        class CustomFormatter(DefaultPromptFormatter):
            def __init__(self, prompt_string):
                super(CustomFormatter, self).__init__(prompt_string)
                self['via_class'] = 'added by custom formatter'

        new_env = copy.deepcopy(self.env)
        with mock_xonsh_env(new_env):
            add_prompt_var('via_func1', 'add_prompt_var before formatter')
            new_env['PROMPT'] = CustomFormatter('{user}:{via_class}:{via_func1}:{via_func2} $')
            add_prompt_var('via_func2', 'add_prompt_var after formatter')
            eq_(new_env['PROMPT'](), 'xonshuser:added by custom formatter:add_prompt_var before formatter:add_prompt_var after formatter $')

