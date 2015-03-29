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

from xonsh.environ import (BasePrompt, DefaultPrompt,
        DEFAULT_PROMPT, DEFAULT_TITLE, add_prompt_var)


class Base_TestPrompt:
    def call_once_func(self):
        self.call_once_counter += 1
        return self.call_once_counter

    def call_every_func(self):
        self.call_every_counter += 1
        return self.call_every_counter

    def setUp(self):
        self.base_prompt = BasePrompt('No vars to substitute')
        self.call_once_counter = 0
        self.call_every_counter = 0

    def check_get_var(self, var_name, expected):
        eq_(self.base_prompt[var_name], expected)


class TestAddPromptVar(Base_TestPrompt):
    def test_add_string_no_call(self):
        self.base_prompt.add_prompt_var('var1', 'value1', call_every=True)
        self.check_get_var('var1', 'value1')
        self.check_get_var('var1', 'value1')

    def test_add_string_with_call(self):
        """ Test that we gracefully handle the case where var is a string and call_every is True"""
        self.base_prompt.add_prompt_var('var2', 'value2', call_every=False)
        self.check_get_var('var2', 'value2')
        self.check_get_var('var2', 'value2')

    def test_add_call_once_func(self):
        self.base_prompt.add_prompt_var('callonce', self.call_once_func, call_every=False)
        self.check_get_var('callonce', 1)
        self.check_get_var('callonce', 1)

    def test_add_call_every_func(self):
        self.base_prompt.add_prompt_var('callevery', self.call_every_func, call_every=True)
        self.check_get_var('callevery', 1)
        self.check_get_var('callevery', 2)


class TestBasePrompt(Base_TestPrompt):
    """ Test that the basics of getting static, callonce, and callevery values works """

    def setUp(self):
        super(TestBasePrompt, self).setUp()
        self.base_prompt['var'] = 'value'
        self.base_prompt['callonce'] = self.call_once_func
        self.base_prompt['callevery'] = self.call_every_func
        self.base_prompt._run_every.add('callevery')

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
        self.check_splat(**self.base_prompt)

class TestDefaultPrompt:
    """Test each of the prompt variables that DefaultPrompt adds"""

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
            self.default_prompt = DefaultPrompt('No vars to substitute')

    def test_get_color(self):
        with mock_xonsh_env(self.env):
            format_vars = frozenset(self.default_prompt.keys())
            ok_(self.color_names.issubset(format_vars))

            assert_in('YELLOW', TERM_COLORS)
            assert_in('YELLOW', self.default_prompt)

            eq_(TERM_COLORS['YELLOW'], self.default_prompt['YELLOW'])

    def test_get_base_cwd(self):
        with mock_xonsh_env(self.env):
            import builtins
            eq_('~', self.default_prompt['base_cwd'])
            builtins.__xonsh_env__['PWD'] = '/home/xonsh/public_html'
            eq_('public_html', self.default_prompt['base_cwd'])
            builtins.__xonsh_env__['PWD'] = '/var/tmp'
            eq_('tmp', self.default_prompt['base_cwd'])

    def test_get_cwd(self):
        with mock_xonsh_env(self.env):
            import builtins
            eq_('~', self.default_prompt['cwd'])
            builtins.__xonsh_env__['PWD'] = '/home/xonsh/public_html'
            eq_('~/public_html', self.default_prompt['cwd'])
            builtins.__xonsh_env__['PWD'] = '/var/tmp'
            eq_('/var/tmp', self.default_prompt['cwd'])

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
            eq_(socket.getfqdn(), self.default_prompt['hostname'])

    def test_short_host_fqdn(self):
        with mock_xonsh_env(self.env):
            # Not a great test default_formatter is such a light wrapper
            # around socket.gethostname that this doesn't really test much
            with mock.patch('socket.gethostname', new=lambda : 'www.example.com'):
                eq_('www', self.default_prompt['short_host'])

    def test_short_host_short(self):
        with mock_xonsh_env(self.env):
            # Not a great test default_formatter is such a light wrapper
            # around socket.gethostname that this doesn't really test much
            with mock.patch('socket.gethostname', new=lambda : 'localhost'):
                eq_('localhost', self.default_prompt['short_host'])

    def test_get_time(self):
        with mock_xonsh_env(self.env):
            now = datetime.now()
            format_reported = self.default_prompt['time']
            ok_(format_reported - now < timedelta(0, 1))
            time.sleep(2)
            now2 = datetime.now()
            ok_(now2 - now > timedelta(0, 2))
            format_reported = self.default_prompt['time']
            ok_(format_reported - now2 < timedelta(0, 1))

    def test_get_user(self):
        with mock_xonsh_env(self.env):
            eq_('xonshuser', self.default_prompt['user'])

    def check_splat(self, **kwargs):
        assert_is_instance(kwargs, dict)
        eq_(len(TERM_COLORS) + 7, len(kwargs))
        kwarg_vars = frozenset(kwargs.keys())
        eq_(self.all_names, kwarg_vars)

    def test_splat(self):
        with mock_xonsh_env(self.env):
            self.check_splat(**self.default_prompt)

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
            self.default_prompt = DefaultPrompt('No prompt vars to substitute')

    def test_individual_formats(self):
        """Test each of the prompt variables that DefaultPromptFormatter adds"""
        with mock_xonsh_env(self.env):
            for name in (n for n in self.all_names if n != 'time'):
                self.default_prompt.prompt_template = r'{%s}' % name
                eq_(self.default_prompt(), self.default_prompt[name])

            now = datetime.now()
            self.default_prompt.prompt_template = r'{time:%Y-%m-%d %H:%M:%S}'
            ok_(datetime.strptime(self.default_prompt(), '%Y-%m-%d %H:%M:%S') - now < timedelta(0, 2))

    def test_default_prompt_template(self):
        """Test that default prompt template expands

        Mainly interested in this not throwing an exception because some
        prompt vars in the default prompt do not have a corresponding
        implementation in the DefaultPrompt Will detect a few other errors as
        well but it's not intended to be complete about those.
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
            self.default_prompt.prompt_template = DEFAULT_PROMPT
            ok_(self.default_prompt().startswith(prompt_start))
            ok_(self.default_prompt().endswith(prompt_end))

    def test_default_title(self):
        """Test that default title string expands

        Mainly interested in this not throwing an exception because some
        prompt vars in the default title do not have a corresponding
        implementation in the DefaultPrompt Will detect a few other errors as
        well but it's not intended to be complete about those.
        """
        with mock_xonsh_env(self.env):
            prompt = 'xonshuser@{}: ~ | xonsh'.format(socket.getfqdn())
            self.default_prompt.prompt_template = DEFAULT_TITLE
            eq_(self.default_prompt(), prompt)

    def test_custom_prompt(self):

        class CustomPrompt(DefaultPrompt):
            def __init__(self, prompt_template):
                super(CustomPrompt, self).__init__(prompt_template)
                self['via_class'] = 'added by custom formatter'

        new_env = copy.deepcopy(self.env)
        with mock_xonsh_env(new_env):
            add_prompt_var('via_func1', 'add_prompt_var before formatter')
            new_env['PROMPT'] = CustomPrompt('{user}:{via_class}:{via_func1}:{via_func2} $')
            add_prompt_var('via_func2', 'add_prompt_var after formatter')
            eq_(new_env['PROMPT'](), 'xonshuser:added by custom formatter:add_prompt_var before formatter:add_prompt_var after formatter $')

