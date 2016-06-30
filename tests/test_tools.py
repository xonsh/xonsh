# -*- coding: utf-8 -*-
"""Tests xonsh tools."""
import os
import pathlib
from tempfile import TemporaryDirectory
import stat
import builtins

import pytest

from xonsh.platform import ON_WINDOWS
from xonsh.lexer import Lexer

from xonsh.tools import (
    EnvPath, always_false, always_true, argvquote,
    bool_or_int_to_str, bool_to_str, check_for_partial_string,
    dynamic_cwd_tuple_to_str, ensure_int_or_slice, ensure_string,
    env_path_to_str, escape_windows_cmd_string, executables_in,
    expand_case_matching, find_next_break, iglobpath, is_bool, is_bool_or_int,
    is_callable, is_dynamic_cwd_width, is_env_path, is_float, is_int,
    is_int_as_str, is_logfile_opt, is_slice_as_str, is_string,
    is_string_or_callable, logfile_opt_to_str, str_to_env_path,
    subexpr_from_unbalanced, subproc_toks, to_bool, to_bool_or_int,
    to_dynamic_cwd_tuple, to_logfile_opt, pathsep_to_set, set_to_pathsep,
    is_string_seq, pathsep_to_seq, seq_to_pathsep, is_nonstring_seq_of_strings,
    pathsep_to_upper_seq, seq_to_upper_pathsep,
    )
from xonsh.commands_cache import CommandsCache
from xonsh.built_ins import expand_path
from xonsh.environ import Env

from tools import mock_xonsh_env

LEXER = Lexer()
LEXER.build()

INDENT = '    '

TOOLS_ENV = {'EXPAND_ENV_VARS': True, 'XONSH_ENCODING_ERRORS':'strict'}
ENCODE_ENV_ONLY = {'XONSH_ENCODING_ERRORS': 'strict'}
PATHEXT_ENV = {'PATHEXT': ['.COM', '.EXE', '.BAT']}

def test_subproc_toks_x():
    exp = '![x]'
    obs = subproc_toks('x', lexer=LEXER, returnline=True)
    assert (exp == obs)


def test_subproc_toks_ls_l():
    exp = '![ls -l]'
    obs = subproc_toks('ls -l', lexer=LEXER, returnline=True)
    assert (exp == obs)


def test_subproc_toks_git():
    s = 'git commit -am "hello doc"'
    exp = '![{0}]'.format(s)
    obs = subproc_toks(s, lexer=LEXER, returnline=True)
    assert (exp == obs)


def test_subproc_toks_git_semi():
    s = 'git commit -am "hello doc"'
    exp = '![{0}];'.format(s)
    obs = subproc_toks(s + ';', lexer=LEXER, returnline=True)
    assert (exp == obs)


def test_subproc_toks_git_nl():
    s = 'git commit -am "hello doc"'
    exp = '![{0}]\n'.format(s)
    obs = subproc_toks(s + '\n', lexer=LEXER, returnline=True)
    assert (exp == obs)


def test_subproc_toks_indent_ls():
    s = 'ls -l'
    exp = INDENT + '![{0}]'.format(s)
    obs = subproc_toks(INDENT + s, mincol=len(INDENT), lexer=LEXER,
                       returnline=True)
    assert (exp == obs)


def test_subproc_toks_indent_ls_nl():
    s = 'ls -l'
    exp = INDENT + '![{0}]\n'.format(s)
    obs = subproc_toks(INDENT + s + '\n', mincol=len(INDENT), lexer=LEXER,
                       returnline=True)
    assert (exp == obs)


def test_subproc_toks_indent_ls_no_min():
    s = 'ls -l'
    exp = INDENT + '![{0}]'.format(s)
    obs = subproc_toks(INDENT + s, lexer=LEXER, returnline=True)
    assert (exp == obs)


def test_subproc_toks_indent_ls_no_min_nl():
    s = 'ls -l'
    exp = INDENT + '![{0}]\n'.format(s)
    obs = subproc_toks(INDENT + s + '\n', lexer=LEXER, returnline=True)
    assert (exp == obs)


def test_subproc_toks_indent_ls_no_min_semi():
    s = 'ls'
    exp = INDENT + '![{0}];'.format(s)
    obs = subproc_toks(INDENT + s + ';', lexer=LEXER, returnline=True)
    assert (exp == obs)


def test_subproc_toks_indent_ls_no_min_semi_nl():
    s = 'ls'
    exp = INDENT + '![{0}];\n'.format(s)
    obs = subproc_toks(INDENT + s + ';\n', lexer=LEXER, returnline=True)
    assert (exp == obs)


def test_subproc_toks_ls_comment():
    s = 'ls -l'
    com = '  # lets list'
    exp = '![{0}]{1}'.format(s, com)
    obs = subproc_toks(s + com, lexer=LEXER, returnline=True)
    assert (exp == obs)


def test_subproc_toks_ls_42_comment():
    s = 'ls 42'
    com = '  # lets list'
    exp = '![{0}]{1}'.format(s, com)
    obs = subproc_toks(s + com, lexer=LEXER, returnline=True)
    assert (exp == obs)


def test_subproc_toks_ls_str_comment():
    s = 'ls "wakka"'
    com = '  # lets list'
    exp = '![{0}]{1}'.format(s, com)
    obs = subproc_toks(s + com, lexer=LEXER, returnline=True)
    assert (exp == obs)


def test_subproc_toks_indent_ls_comment():
    ind = '    '
    s = 'ls -l'
    com = '  # lets list'
    exp = '{0}![{1}]{2}'.format(ind, s, com)
    obs = subproc_toks(ind + s + com, lexer=LEXER, returnline=True)
    assert (exp == obs)


def test_subproc_toks_indent_ls_str():
    ind = '    '
    s = 'ls "wakka"'
    com = '  # lets list'
    exp = '{0}![{1}]{2}'.format(ind, s, com)
    obs = subproc_toks(ind + s + com, lexer=LEXER, returnline=True)
    assert (exp == obs)


def test_subproc_toks_ls_l_semi_ls_first():
    lsdl = 'ls -l'
    ls = 'ls'
    s = '{0}; {1}'.format(lsdl, ls)
    exp = '![{0}]; {1}'.format(lsdl, ls)
    obs = subproc_toks(s, lexer=LEXER, maxcol=6, returnline=True)
    assert (exp == obs)


def test_subproc_toks_ls_l_semi_ls_second():
    lsdl = 'ls -l'
    ls = 'ls'
    s = '{0}; {1}'.format(lsdl, ls)
    exp = '{0}; ![{1}]'.format(lsdl, ls)
    obs = subproc_toks(s, lexer=LEXER, mincol=7, returnline=True)
    assert (exp == obs)


def test_subproc_toks_hello_mom_first():
    fst = "echo 'hello'"
    sec = "echo 'mom'"
    s = '{0}; {1}'.format(fst, sec)
    exp = '![{0}]; {1}'.format(fst, sec)
    obs = subproc_toks(s, lexer=LEXER, maxcol=len(fst)+1, returnline=True)
    assert (exp == obs)


def test_subproc_toks_hello_mom_second():
    fst = "echo 'hello'"
    sec = "echo 'mom'"
    s = '{0}; {1}'.format(fst, sec)
    exp = '{0}; ![{1}]'.format(fst, sec)
    obs = subproc_toks(s, lexer=LEXER, mincol=len(fst), returnline=True)
    assert (exp == obs)


def test_subproc_toks_comment():
    exp = None
    obs = subproc_toks('# I am a comment', lexer=LEXER, returnline=True)
    assert (exp == obs)


def test_subproc_toks_not():
    exp = 'not ![echo mom]'
    obs = subproc_toks('not echo mom', lexer=LEXER, returnline=True)
    assert (exp == obs)


def test_subproc_toks_paren():
    exp = '(![echo mom])'
    obs = subproc_toks('(echo mom)', lexer=LEXER, returnline=True)
    assert (exp == obs)


def test_subproc_toks_paren_ws():
    exp = '(![echo mom])  '
    obs = subproc_toks('(echo mom)  ', lexer=LEXER, returnline=True)
    assert (exp == obs)


def test_subproc_toks_not_paren():
    exp = 'not (![echo mom])'
    obs = subproc_toks('not (echo mom)', lexer=LEXER, returnline=True)
    assert (exp == obs)


def test_subproc_toks_and_paren():
    exp = 'True and (![echo mom])'
    obs = subproc_toks('True and (echo mom)', lexer=LEXER, returnline=True)
    assert (exp == obs)


def test_subproc_toks_paren_and_paren():
    exp = '(![echo a]) and (echo b)'
    obs = subproc_toks('(echo a) and (echo b)', maxcol=9, lexer=LEXER, returnline=True)
    assert (exp == obs)


def test_subproc_toks_semicolon_only():
    exp = None
    obs = subproc_toks(';', lexer=LEXER, returnline=True)
    assert (exp == obs)


def test_subproc_toks_pyeval():
    s = 'echo @(1+1)'
    exp = '![{0}]'.format(s)
    obs = subproc_toks(s, lexer=LEXER, returnline=True)
    assert (exp == obs)


def test_subproc_toks_twopyeval():
    s = 'echo @(1+1) @(40 + 2)'
    exp = '![{0}]'.format(s)
    obs = subproc_toks(s, lexer=LEXER, returnline=True)
    assert (exp == obs)


def test_subproc_toks_pyeval_parens():
    s = 'echo @(1+1)'
    inp = '({0})'.format(s)
    exp = '(![{0}])'.format(s)
    obs = subproc_toks(inp, lexer=LEXER, returnline=True)
    assert (exp == obs)


def test_subproc_toks_twopyeval_parens():
    s = 'echo @(1+1) @(40+2)'
    inp = '({0})'.format(s)
    exp = '(![{0}])'.format(s)
    obs = subproc_toks(inp, lexer=LEXER, returnline=True)
    assert (exp == obs)


def test_subproc_toks_pyeval_nested():
    s = 'echo @(min(1, 42))'
    exp = '![{0}]'.format(s)
    obs = subproc_toks(s, lexer=LEXER, returnline=True)
    assert (exp == obs)


def test_subproc_toks_pyeval_nested_parens():
    s = 'echo @(min(1, 42))'
    inp = '({0})'.format(s)
    exp = '(![{0}])'.format(s)
    obs = subproc_toks(inp, lexer=LEXER, returnline=True)
    assert (exp == obs)


def test_subproc_toks_capstdout():
    s = 'echo $(echo bat)'
    exp = '![{0}]'.format(s)
    obs = subproc_toks(s, lexer=LEXER, returnline=True)
    assert (exp == obs)


def test_subproc_toks_capproc():
    s = 'echo !(echo bat)'
    exp = '![{0}]'.format(s)
    obs = subproc_toks(s, lexer=LEXER, returnline=True)
    assert (exp == obs)


def test_subproc_toks_pyeval_redirect():
    s = 'echo @("foo") > bar'
    inp = '{0}'.format(s)
    exp = '![{0}]'.format(s)
    obs = subproc_toks(inp, lexer=LEXER, returnline=True)
    assert (exp == obs)


def test_subexpr_from_unbalanced_parens():
    cases = [
        ('f(x.', 'x.'),
        ('f(1,x.', 'x.'),
        ('f((1,10),x.y', 'x.y'),
        ]
    for expr, exp in cases:
        obs = subexpr_from_unbalanced(expr, '(', ')')
        assert exp == obs


def test_find_next_break():
    cases = [
        ('ls && echo a', 0, 4),
        ('ls && echo a', 6, None),
        ('ls && echo a || echo b', 6, 14),
        ('(ls) && echo a', 1, 4),
        ('not ls && echo a', 0, 8),
        ('not (ls) && echo a', 0, 8),
        ]
    for line, mincol, exp in cases:
        obs = find_next_break(line, mincol=mincol, lexer=LEXER)
        assert exp == obs


def test_iglobpath():
    with TemporaryDirectory() as test_dir:
        # Create files 00.test to 99.test in unsorted order
        num = 18
        for _ in range(100):
            s = str(num).zfill(2)
            path = os.path.join(test_dir, s + '.test')
            with open(path, 'w') as file:
                file.write(s + '\n')
            num = (num + 37) % 100

        # Create one file not matching the '*.test'
        with open(os.path.join(test_dir, '07'), 'w') as file:
            file.write('test\n')

        with mock_xonsh_env(Env(EXPAND_ENV_VARS=False)):
            builtins.__xonsh_expand_path__ = expand_path

            paths = list(iglobpath(os.path.join(test_dir, '*.test'),
                                   ignore_case=False, sort_result=False))
            assert len(paths) == 100
            paths = list(iglobpath(os.path.join(test_dir, '*'),
                                   ignore_case=True, sort_result=False))
            assert len(paths) == 101

            paths = list(iglobpath(os.path.join(test_dir, '*.test'),
                                   ignore_case=False, sort_result=True))
            assert len(paths) == 100
            assert paths == sorted(paths)
            paths = list(iglobpath(os.path.join(test_dir, '*'),
                                   ignore_case=True, sort_result=True))
            assert len(paths) == 101
            assert paths == sorted(paths)


def test_is_int():
    cases = [
        (42, True),
        (42.0, False),
        ('42', False),
        ('42.0', False),
        ([42], False),
        ([], False),
        (None, False),
        ('', False)
        ]
    for inp, exp in cases:
        obs = is_int(inp)
        assert exp == obs


def test_is_int_as_str():
    cases = [
        ('42', True),
        ('42.0', False),
        (42, False),
        ([42], False),
        ([], False),
        (None, False),
        ('', False),
        (False, False),
        (True, False),
        ]
    for inp, exp in cases:
        obs = is_int_as_str(inp)
        assert exp == obs


def test_is_float():
    cases = [
        (42.0, True),
        (42.000101010010101010101001010101010001011100001101101011100, True),
        (42, False),
        ('42', False),
        ('42.0', False),
        ([42], False),
        ([], False),
        (None, False),
        ('', False),
        (False, False),
        (True, False),
        ]
    for inp, exp in cases:
        obs = is_float(inp)
        assert exp == obs


def test_is_slice_as_str():
    cases = [
        (42, False),
        (None, False),
        ('42', False),
        ('-42', False),
        (slice(1, 2, 3), False),
        ([], False),
        (False, False),
        (True, False),
        ('1:2:3', True),
        ('1::3', True),
        ('1:', True),
        (':', True),
        ('[1:2:3]', True),
        ('(1:2:3)', True),
        ('r', False),
        ('r:11', False),
        ]
    for inp, exp in cases:
        obs = is_slice_as_str(inp)
        assert exp == obs


def test_is_string():
    assert is_string('42.0')
    assert not is_string(42.0)


def test_is_callable():
    assert is_callable(lambda: 42.0)
    assert not is_callable(42.0)


def test_is_string_or_callable():
    assert is_string_or_callable('42.0')
    assert is_string_or_callable(lambda: 42.0)
    assert not is_string(42.0)


def test_always_true():
    assert always_true(42)
    assert always_true('42')


def test_always_false():
    assert not always_false(42)
    assert not always_false('42')


def test_ensure_string():
    cases = [
        (42, '42'),
        ('42', '42'),
        ]
    for inp, exp in cases:
        obs = ensure_string(inp)
        assert exp == obs


def test_pathsep_to_set():
    cases = [
        ('', set()),
        ('a', {'a'}),
        (os.pathsep.join(['a', 'b']), {'a', 'b'}),
        (os.pathsep.join(['a', 'b', 'c']), {'a', 'b', 'c'}),
        ]
    for inp, exp in cases:
        obs = pathsep_to_set(inp)
        assert exp == obs


def test_set_to_pathsep():
    cases = [
        (set(), ''),
        ({'a'}, 'a'),
        ({'a', 'b'}, os.pathsep.join(['a', 'b'])),
        ({'a', 'b', 'c'}, os.pathsep.join(['a', 'b', 'c'])),
        ]
    for inp, exp in cases:
        obs = set_to_pathsep(inp, sort=(len(inp) > 1))
        assert exp == obs


def test_is_string_seq():
    assert is_string_seq('42.0')
    assert is_string_seq(['42.0'])
    assert not is_string_seq([42.0])


def test_is_nonstring_seq_of_strings():
    assert not is_nonstring_seq_of_strings('42.0')
    assert is_nonstring_seq_of_strings(['42.0'])
    assert not is_nonstring_seq_of_strings([42.0])


def test_pathsep_to_seq():
    cases = [
        ('', []),
        ('a', ['a']),
        (os.pathsep.join(['a', 'b']), ['a', 'b']),
        (os.pathsep.join(['a', 'b', 'c']), ['a', 'b', 'c']),
        ]
    for inp, exp in cases:
        obs = pathsep_to_seq(inp)
        assert exp == obs


def test_seq_to_pathsep():
    cases = [
        ([], ''),
        (['a'], 'a'),
        (['a', 'b'], os.pathsep.join(['a', 'b'])),
        (['a', 'b', 'c'], os.pathsep.join(['a', 'b', 'c'])),
        ]
    for inp, exp in cases:
        obs = seq_to_pathsep(inp)
        assert exp == obs


def test_pathsep_to_upper_seq():
    cases = [
        ('', []),
        ('a', ['A']),
        (os.pathsep.join(['a', 'B']), ['A', 'B']),
        (os.pathsep.join(['A', 'b', 'c']), ['A', 'B', 'C']),
        ]
    for inp, exp in cases:
        obs = pathsep_to_upper_seq(inp)
        assert exp == obs


def test_seq_to_upper_pathsep():
    cases = [
        ([], ''),
        (['a'], 'A'),
        (['a', 'b'], os.pathsep.join(['A', 'B'])),
        (['a', 'B', 'c'], os.pathsep.join(['A', 'B', 'C'])),
        ]
    for inp, exp in cases:
        obs = seq_to_upper_pathsep(inp)
        assert exp == obs


def test_is_env_path():
    cases = [
        ('/home/wakka', False),
        (['/home/jawaka'], False),
        (EnvPath(['/home/jawaka']), True),
        (EnvPath(['jawaka']), True),
        (EnvPath(b'jawaka:wakka'), True),
        ]
    for inp, exp in cases:
        obs = is_env_path(inp)
        assert exp == obs


def test_str_to_env_path():
    cases = [
        ('/home/wakka', ['/home/wakka']),
        ('/home/wakka' + os.pathsep + '/home/jawaka',
         ['/home/wakka', '/home/jawaka']),
        (b'/home/wakka', ['/home/wakka']),
        ]
    for inp, exp in cases:
        obs = str_to_env_path(inp)
        assert exp == obs.paths


def test_env_path_to_str():
    cases = [
        (['/home/wakka'], '/home/wakka'),
        (['/home/wakka', '/home/jawaka'],
         '/home/wakka' + os.pathsep + '/home/jawaka'),
        ]
    for inp, exp in cases:
        obs = env_path_to_str(inp)
        assert exp == obs


def test_env_path():
    def expand(path):
        return os.path.expanduser(os.path.expandvars(path))

    getitem_cases = [
        ('xonsh_dir', 'xonsh_dir'),
        ('.', '.'),
        ('../', '../'),
        ('~/', '~/'),
        (b'~/../', '~/../'),
    ]
    with mock_xonsh_env(TOOLS_ENV):
        for inp, exp in getitem_cases:
            obs = EnvPath(inp)[0] # call to __getitem__
            assert expand(exp) == obs

    with mock_xonsh_env(ENCODE_ENV_ONLY):
        for inp, exp in getitem_cases:
            obs = EnvPath(inp)[0] # call to __getitem__
            assert exp == obs

    # cases that involve path-separated strings
    multipath_cases = [
        (os.pathsep.join(['xonsh_dir', '../', '.', '~/']),
         ['xonsh_dir', '../', '.', '~/']),
        ('/home/wakka' + os.pathsep + '/home/jakka' + os.pathsep + '~/',
         ['/home/wakka', '/home/jakka', '~/'])
    ]
    with mock_xonsh_env(TOOLS_ENV):
        for inp, exp in multipath_cases:
            obs = [i for i in EnvPath(inp)]
            assert [expand(i) for i in exp] == obs

    with mock_xonsh_env(ENCODE_ENV_ONLY):
        for inp, exp in multipath_cases:
            obs = [i for i in EnvPath(inp)]
            assert [i for i in exp] == obs

    # cases that involve pathlib.Path objects
    pathlib_cases = [
        (pathlib.Path('/home/wakka'), ['/home/wakka'.replace('/', os.sep)]),
        (pathlib.Path('~/'), ['~']),
        (pathlib.Path('.'), ['.']),
        (['/home/wakka', pathlib.Path('/home/jakka'), '~/'],
         ['/home/wakka', '/home/jakka'.replace('/', os.sep), '~/']),
        (['/home/wakka', pathlib.Path('../'), '../'],
         ['/home/wakka', '..', '../']),
        (['/home/wakka', pathlib.Path('~/'), '~/'],
         ['/home/wakka', '~', '~/']),
    ]

    with mock_xonsh_env(TOOLS_ENV):
        for inp, exp in pathlib_cases:
            # iterate over EnvPath to acquire all expanded paths
            obs = [i for i in EnvPath(inp)]
            assert [expand(i) for i in exp] == obs

def test_env_path_slices():
    # build os-dependent paths properly
    def mkpath(*paths):
        return os.sep + os.sep.join(paths)

    # get all except the last element in a slice
    slice_last = [
        ([mkpath('home', 'wakka'),
          mkpath('home', 'jakka'),
          mkpath('home', 'yakka')],
         [mkpath('home', 'wakka'),
          mkpath('home', 'jakka')])]

    for inp, exp in slice_last:
        obs = EnvPath(inp)[:-1]
        assert exp == obs

    # get all except the first element in a slice
    slice_first = [
        ([mkpath('home', 'wakka'),
          mkpath('home', 'jakka'),
          mkpath('home', 'yakka')],
         [mkpath('home', 'jakka'),
          mkpath('home', 'yakka')])]

    for inp, exp in slice_first:
        obs = EnvPath(inp)[1:]
        assert exp == obs

    # slice paths with a step
    slice_step = [
        ([mkpath('home', 'wakka'),
          mkpath('home', 'jakka'),
          mkpath('home', 'yakka'),
          mkpath('home', 'takka')],
         [mkpath('home', 'wakka'),
          mkpath('home', 'yakka')],
         [mkpath('home', 'jakka'),
          mkpath('home', 'takka')])]

    for inp, exp_a, exp_b in slice_step:
        obs_a = EnvPath(inp)[0::2]
        assert exp_a == obs_a
        obs_b = EnvPath(inp)[1::2]
        assert exp_b == obs_b

    # keep only non-home paths
    slice_normal = [
        ([mkpath('home', 'wakka'),
          mkpath('home', 'xakka'),
          mkpath('other', 'zakka'),
          mkpath('another', 'akka'),
          mkpath('home', 'bakka')],
         [mkpath('other', 'zakka'),
          mkpath('another', 'akka')])]

    for inp, exp in slice_normal:
        obs = EnvPath(inp)[2:4]
        assert exp == obs


def test_is_bool():
    assert True == is_bool(True)
    assert True == is_bool(False)
    assert False == is_bool(1)
    assert False == is_bool('yooo hooo!')


def test_to_bool():
    cases = [
        (True, True),
        (False, False),
        (None, False),
        ('', False),
        ('0', False),
        ('False', False),
        ('NONE', False),
        ('TRUE', True),
        ('1', True),
        (0, False),
        (1, True),
        ]
    for inp, exp in cases:
        obs = to_bool(inp)
        assert exp == obs


def test_bool_to_str():
    assert '1' == bool_to_str(True)
    assert '' == bool_to_str(False)


def test_is_bool_or_int():
    cases = [
        (True, True),
        (False, True),
        (1, True),
        (0, True),
        ('Yolo', False),
        (1.0, False),
        ]
    for inp, exp in cases:
        obs = is_bool_or_int(inp)
        assert exp == obs


def test_to_bool_or_int():
    cases = [
        (True, True),
        (False, False),
        (1, 1),
        (0, 0),
        ('', False),
        (0.0, False),
        (1.0, True),
        ('T', True),
        ('f', False),
        ('0', 0),
        ('10', 10),
        ]
    for inp, exp in cases:
        obs = to_bool_or_int(inp)
        assert exp == obs


def test_bool_or_int_to_str():
    cases = [
        (True, '1'),
        (False, ''),
        (1, '1'),
        (0, '0'),
        ]
    for inp, exp in cases:
        obs = bool_or_int_to_str(inp)
        assert exp == obs


def test_ensure_int_or_slice():
    cases = [
        (42, 42),
        (None, slice(None, None, None)),
        ('42', 42),
        ('-42', -42),
        ('1:2:3', slice(1, 2, 3)),
        ('1::3', slice(1, None, 3)),
        (':', slice(None, None, None)),
        ('1:', slice(1, None, None)),
        ('[1:2:3]', slice(1, 2, 3)),
        ('(1:2:3)', slice(1, 2, 3)),
        ('r', False),
        ('r:11', False),
        ]
    for inp, exp in cases:
        obs = ensure_int_or_slice(inp)
        assert exp == obs


def test_is_dynamic_cwd_width():
    cases = [
        ('20', False),
        ('20%', False),
        ((20, 'c'), False),
        ((20.0, 'm'), False),
        ((20.0, 'c'), True),
        ((20.0, '%'), True),
        ]
    for inp, exp in cases:
        obs = is_dynamic_cwd_width(inp)
        assert exp == obs


def test_is_logfile_opt():
    cases = [
        ('throwback.log', True),
        ('', True),
        (None, True),
        (True, False),
        (False, False),
        (42, False),
        ([1, 2, 3], False),
        ((1, 2), False),
        (("wrong", "parameter"), False)
    ]
    if not ON_WINDOWS:
        cases.append(('/dev/null', True))
    for inp, exp in cases:
        obs = is_logfile_opt(inp)
        assert exp == obs


def test_to_logfile_opt():
    cases = [
        (True, None),
        (False, None),
        (1, None),
        (None, None),
        ('throwback.log', 'throwback.log'),
    ]
    if not ON_WINDOWS:
        cases.append(('/dev/null', '/dev/null'))
        cases.append(('/dev/nonexistent_dev', None))
    for inp, exp in cases:
        obs = to_logfile_opt(inp)
        assert exp == obs


def test_logfile_opt_to_str():
    cases = [
        (None, ''),
        ('', ''),
        ('throwback.log', 'throwback.log'),
        ('/dev/null', '/dev/null')
    ]
    for inp, exp in cases:
        obs = logfile_opt_to_str(inp)
        assert exp == obs


def test_to_dynamic_cwd_tuple():
    cases = [
        ('20', (20.0, 'c')),
        ('20%', (20.0, '%')),
        ((20, 'c'), (20.0, 'c')),
        ((20, '%'), (20.0, '%')),
        ((20.0, 'c'), (20.0, 'c')),
        ((20.0, '%'), (20.0, '%')),
        ('inf', (float('inf'), 'c')),
        ]
    for inp, exp in cases:
        obs = to_dynamic_cwd_tuple(inp)
        assert exp == obs


def test_dynamic_cwd_tuple_to_str():
    cases = [
        ((20.0, 'c'), '20.0'),
        ((20.0, '%'), '20.0%'),
        ((float('inf'), 'c'), 'inf'),
        ]
    for inp, exp in cases:
        obs = dynamic_cwd_tuple_to_str(inp)
        assert exp == obs


def test_escape_windows_cmd_string():
    cases = [
        ('', ''),
        ('foo', 'foo'),
        ('foo&bar', 'foo^&bar'),
        ('foo$?-/_"\\', 'foo$?-/_^"\\'),
        ('^&<>|', '^^^&^<^>^|'),
        ('this /?', 'this /.')
        ]
    for st, esc in cases:
        obs = escape_windows_cmd_string(st)
        assert esc == obs


def test_argvquote():
    cases = [
        ('', '""'),
        ('foo', 'foo'),
        (r'arg1 "hallo, "world""  "\some\path with\spaces")',
         r'"arg1 \"hallo, \"world\"\"  \"\some\path with\spaces\")"'),
        (r'"argument"2" argument3 argument4',
         r'"\"argument\"2\" argument3 argument4"'),
        (r'"\foo\bar bar\foo\" arg',
         r'"\"\foo\bar bar\foo\\\" arg"')
        ]
    for st, esc in cases:
        obs = argvquote(st)
        assert esc == obs


_leaders = ('', 'not empty')
_r = ('r', '')
_b = ('b', '')
_u = ('u', '')
_chars = set(i+j+k for i in _r for j in _b for k in _u)
_chars |= set(i+j+k for i in _r for j in _u for k in _b)
_chars |= set(i+j+k for i in _b for j in _u for k in _r)
_chars |= set(i+j+k for i in _b for j in _r for k in _u)
_chars |= set(i+j+k for i in _u for j in _r for k in _b)
_chars |= set(i+j+k for i in _u for j in _b for k in _r)
_squote = ('"""', '"', "'''", "'")
_startend = {c+s: s for c in _chars for s in _squote}

inners = "this is a string"


def test_partial_string():
    # single string at start
    assert check_for_partial_string('no strings here') == (None, None, None)
    assert check_for_partial_string('') == (None, None, None)
    for s, e in _startend.items():
        _test = s + inners + e
        for l in _leaders:
            for f in _leaders:
                # single string
                _res = check_for_partial_string(l + _test + f)
                assert _res == (len(l), len(l) + len(_test), s)
                # single partial
                _res = check_for_partial_string(l + f + s + inners)
                assert _res == (len(l+f), None, s)
                for s2, e2 in _startend.items():
                    _test2 = s2 + inners + e2
                    for l2 in _leaders:
                        for f2 in _leaders:
                            # two strings
                            _res = check_for_partial_string(l + _test + f + l2 + _test2 + f2)
                            assert _res == (len(l+_test+f+l2), len(l+_test+f+l2+_test2), s2)
                            # one string, one partial
                            _res = check_for_partial_string(l + _test + f + l2 + s2 + inners)
                            assert _res == (len(l+_test+f+l2), None, s2)


def test_executables_in():
    expected = set()
    types = ('file', 'directory', 'brokensymlink')
    if ON_WINDOWS:
        # Don't test symlinks on windows since it requires admin
        types = ('file', 'directory')
    executables = (True, False)
    with TemporaryDirectory() as test_path:
        for _type in types:
            for executable in executables:
                fname = '%s_%s' % (_type, executable)
                if _type == 'none':
                    continue
                if _type == 'file' and executable:
                    ext = '.exe' if ON_WINDOWS else ''
                    expected.add(fname + ext)
                else:
                    ext = ''
                path = os.path.join(test_path, fname + ext)
                if _type == 'file':
                    with open(path, 'w') as f:
                        f.write(fname)
                elif _type == 'directory':
                    os.mkdir(path)
                elif _type == 'brokensymlink':
                    tmp_path = os.path.join(test_path, 'i_wont_exist')
                    with open(tmp_path, 'w') as f:
                        f.write('deleteme')
                        os.symlink(tmp_path, path)
                    os.remove(tmp_path)
                if executable and not _type == 'brokensymlink':
                    os.chmod(path, stat.S_IXUSR | stat.S_IRUSR | stat.S_IWUSR)
            if ON_WINDOWS:
                with mock_xonsh_env(PATHEXT_ENV):
                    result = set(executables_in(test_path))
            else:
                result = set(executables_in(test_path))
    assert (expected == result)


def test_expand_case_matching():
    cases = {
        'yo': '[Yy][Oo]',
        '[a-f]123e': '[a-f]123[Ee]',
        '${HOME}/yo': '${HOME}/[Yy][Oo]',
        './yo/mom': './[Yy][Oo]/[Mm][Oo][Mm]',
        'Eßen': '[Ee][Ss]?[Ssß][Ee][Nn]',
        }
    for inp, exp in cases.items():
        obs = expand_case_matching(inp)
        assert exp == obs


def test_commands_cache_lazy():
    cc = CommandsCache()
    assert not cc.lazyin('xonsh')
    assert 0 == len(list(cc.lazyiter()))
    assert 0 == cc.lazylen()
