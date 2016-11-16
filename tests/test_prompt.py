import os
import subprocess as sp
from unittest.mock import Mock

import pytest

from xonsh.environ import Env
from xonsh.prompt.base import PromptFormatter
from xonsh.prompt import vc

from tools import skip_if_py34, DummyEnv


@pytest.fixture
def formatter(xonsh_builtins):
    return PromptFormatter()


@pytest.mark.parametrize('fields', [{
    'a_string': 'cat',
    'none': (lambda: None),
    'f': (lambda: 'wakka'),
}])
@pytest.mark.parametrize('inp, exp', [
    ('my {a_string}', 'my cat'),
    ('my {none}{a_string}', 'my cat'),
    ('{f} jawaka', 'wakka jawaka'),
])
def test_format_prompt(inp, exp, fields, formatter):
    obs = formatter(template=inp, fields=fields)
    assert exp == obs


@pytest.mark.parametrize('fields', [{
    'a_string': 'cats',
    'a_number': 7,
    'empty': '',
    'current_job': (lambda: 'sleep'),
    'none': (lambda: None),
}])
@pytest.mark.parametrize('inp, exp', [
    ('{a_number:{0:^3}}cats', ' 7 cats'),
    ('{current_job:{} | }xonsh', 'sleep | xonsh'),
    ('{none:{} | }{a_string}{empty:!}', 'cats!'),
    ('{none:{}}', ''),
    ('{{{a_string:{{{}}}}}}', '{{cats}}'),
    ('{{{none:{{{}}}}}}', '{}'),
])
def test_format_prompt_with_format_spec(inp, exp, fields, formatter):
    obs = formatter(template=inp, fields=fields)
    assert exp == obs


def test_format_prompt_with_broken_template(formatter):
    for p in ('{user', '{user}{hostname'):
        assert formatter(p) == p

    # '{{user' will be parsed to '{user'
    for p in ('{{user}', '{{user'):
        assert 'user' in formatter(p)


@pytest.mark.parametrize('inp', [
    '{user',
    '{{user',
    '{{user}',
    '{user}{hostname',
    ])
def test_format_prompt_with_broken_template_in_func(inp, formatter):
    # '{{user' will be parsed to '{user'
    assert '{user' in formatter(lambda: inp)


def test_format_prompt_with_invalid_func(formatter, xonsh_builtins):
    xonsh_builtins.__xonsh_env__ = Env()

    def p():
        foo = bar  # raises exception # noqa
        return '{user}'

    assert isinstance(formatter(p), str)


def test_format_prompt_with_func_that_raises(formatter,
                                             capsys,
                                             xonsh_builtins):
    xonsh_builtins.__xonsh_env__ = Env()
    template = 'tt {zerodiv} tt'
    exp = 'tt (ERROR:zerodiv) tt'
    fields = {'zerodiv': lambda: 1/0}
    obs = formatter(template, fields)
    assert exp == obs
    out, err = capsys.readouterr()
    assert 'prompt: error' in err


def test_promptformatter_cache(formatter):
    spam = Mock()
    template = '{spam} and {spam}'
    fields = {'spam': spam}

    formatter(template, fields)

    assert spam.call_count == 1


def test_promptformatter_clears_cache(formatter):
    spam = Mock()
    template = '{spam} and {spam}'
    fields = {'spam': spam}

    formatter(template, fields)
    formatter(template, fields)

    assert spam.call_count == 2


# vc
@pytest.mark.parametrize('repo', ['hg', 'git'])
def test_test_repos(source_path, repo):
    test_repo = os.path.join(source_path, 'tests', '{}-test-repo'.format(repo))
    assert os.path.isdir(test_repo)
    assert os.path.isdir(os.path.join(test_repo, '.{}'.format(repo)))


@pytest.mark.parametrize('cmd, exp', [
    ('git', 'master'),
    ('hg', 'default'),
    ])
def test_vc_get_branch(cmd, exp, source_path, xonsh_builtins):
    xonsh_builtins.__xonsh_env__ = Env(VC_BRANCH_TIMEOUT=1)
    test_repo = '{}-test-repo'.format(cmd)
    test_repo_path = os.path.join(source_path, 'tests', test_repo)
    os.chdir(test_repo_path)
    # get corresponding function from vc module
    if cmd == 'hg':
        obs = vc.get_hg_branch()
    else:
        obs = vc.get_git_branch()
    assert obs == exp


def test_vc_current_branch_calls_commands_cache_locate_binary_once(xonsh_builtins):
    # it's actually two times, once for hg and once for git
    # maybe the function needs to be split
    xonsh_builtins.__xonsh_env__ = DummyEnv(VC_BRANCH_TIMEOUT=1)
    cache_mock = Mock()
    xonsh_builtins.__xonsh_commands_cache__ = cache_mock
    # case where lazy locate returns nothing
    llb_mock = Mock(return_value='')
    cache_mock.lazy_locate_binary = llb_mock

    vc.current_branch() # calls locate_binary twice (hg, git)
    vc.current_branch() # should not call locate_binary

    assert cache_mock.locate_binary.call_count == 2
