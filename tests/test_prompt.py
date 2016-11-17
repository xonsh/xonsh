import os
import subprocess as sp
import tempfile
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


# Xonsh interaction with version control systems.
VC_BRANCH = {'git': 'master',
             'hg': 'default'}


@pytest.yield_fixture(scope='module', params=VC_BRANCH.keys())
def test_repo(request):
    """Return the vc and a temporary dir that is a repository for testing."""
    vc = request.param
    with tempfile.TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)
        sp.call([vc, 'init'])
        # git needs at least one commit
        if vc == 'git':
            sp.call(['touch', 'empty'])
            sp.call(['git', 'add', 'empty'])
            sp.call(['git', 'commit', '-m', '"test commit"'])
        yield vc, temp_dir


def test_testing_repos(test_repo):
    assert os.path.isdir(os.path.join(test_repo[1], '.{}'.format(test_repo[0])))


def test_vc_get_branch(test_repo, xonsh_builtins):
    xonsh_builtins.__xonsh_env__ = Env(VC_BRANCH_TIMEOUT=1)
    os.chdir(test_repo[1])
    # get corresponding function from vc module
    fun = 'get_{}_branch'.format(test_repo[0])
    obs = getattr(vc, fun)()
    assert obs == VC_BRANCH[test_repo[0]]


def test_vc_current_branch_calls_commands_cache_locate_binary_once(xonsh_builtins):
    # it's actually two times, once for hg and once for git
    # maybe the function needs to be split
    xonsh_builtins.__xonsh_env__ = DummyEnv(VC_BRANCH_TIMEOUT=1)
    cache_mock = Mock()
    xonsh_builtins.__xonsh_commands_cache__ = cache_mock
    # case where lazy locate returns nothing
    llb_mock = Mock(return_value='')
    cache_mock.lazy_locate_binary = llb_mock

    vc.current_branch()  # calls locate_binary twice (hg, git)
    vc.current_branch()  # should not call locate_binary

    assert cache_mock.locate_binary.call_count == 2
