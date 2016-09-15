import pytest

from xonsh.environ import Env
from xonsh.prompt.base import partial_format_prompt


@pytest.mark.parametrize('formatter_dict',[{
    'a_string': 'cat',
    'none': (lambda: None),
    'f': (lambda: 'wakka'),
}])
@pytest.mark.parametrize('inp, exp', [
    ('my {a_string}', 'my cat'),
    ('my {none}{a_string}', 'my cat'),
    ('{f} jawaka', 'wakka jawaka'),
])
def test_format_prompt(inp, exp, formatter_dict, xonsh_builtins):
    obs = partial_format_prompt(template=inp, formatter_dict=formatter_dict)
    assert exp == obs


@pytest.mark.parametrize('formatter_dict',[{
    'a_string': 'cats',
    'a_number': 7,
    'empty': '',
    'current_job': (lambda: 'sleep'),
    'none': (lambda: None),
}])
@pytest.mark.parametrize('inp, exp', [
    ('{a_number:{0:^3}}cats', ' 7 cats'),
    ( '{current_job:{} | }xonsh', 'sleep | xonsh'),
    ( '{none:{} | }{a_string}{empty:!}', 'cats!'),
    ( '{none:{}}', ''),
    ( '{{{a_string:{{{}}}}}}', '{{cats}}'),
    ( '{{{none:{{{}}}}}}', '{}'),
])
def test_format_prompt_with_format_spec(inp, exp, formatter_dict, xonsh_builtins):
    obs = partial_format_prompt(template=inp, formatter_dict=formatter_dict)
    assert exp == obs


def test_format_prompt_with_broken_template(xonsh_builtins):
    for p in ('{user', '{user}{hostname'):
        assert partial_format_prompt(p) == p

    # '{{user' will be parsed to '{user'
    for p in ('{{user}', '{{user'):
        assert 'user' in partial_format_prompt(p)


def test_format_prompt_with_broken_template_in_func(xonsh_builtins):
    for p in (
        lambda: '{user',
        lambda: '{{user',
        lambda: '{{user}',
        lambda: '{user}{hostname',
    ):
        # '{{user' will be parsed to '{user'
        assert 'user' in partial_format_prompt(p)


def test_format_prompt_with_invalid_func(xonsh_builtins):
    xonsh_builtins.__xonsh_env__ = Env()
    def p():
        foo = bar  # raises exception
        return '{user}'
    assert isinstance(partial_format_prompt(p), str)


def test_format_prompt_with_func_that_raises(capsys, xonsh_builtins):
    xonsh_builtins.__xonsh_env__ = Env()
    template = 'tt {zerodiv} tt'
    exp = 'tt (ERROR:zerodiv) tt'
    formatter_dict = {'zerodiv': lambda : 1/0}
    obs = partial_format_prompt(template, formatter_dict)
    assert exp == obs
    out, err = capsys.readouterr()
    assert 'prompt: error' in err
