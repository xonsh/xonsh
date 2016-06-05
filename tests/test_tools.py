# -*- coding: utf-8 -*-
"""Tests the xonsh lexer."""
import os
from tempfile import TemporaryDirectory
import stat

import nose
from nose.tools import assert_equal, assert_true, assert_false

from xonsh.platform import ON_WINDOWS
from xonsh.lexer import Lexer
from xonsh.tools import (
    subproc_toks, subexpr_from_unbalanced, is_int, always_true, always_false,
    ensure_string, is_env_path, str_to_env_path, env_path_to_str,
    escape_windows_cmd_string, is_bool, to_bool, bool_to_str,
    is_bool_or_int, to_bool_or_int, bool_or_int_to_str,
    ensure_int_or_slice, is_float, is_string, is_callable,
    is_string_or_callable, check_for_partial_string,
    is_dynamic_cwd_width, to_dynamic_cwd_tuple, dynamic_cwd_tuple_to_str,
    argvquote, executables_in, find_next_break, expand_case_matching)

LEXER = Lexer()
LEXER.build()

INDENT = '    '


def test_subproc_toks_x():
    exp = '![x]'
    obs = subproc_toks('x', lexer=LEXER, returnline=True)
    assert_equal(exp, obs)


def test_subproc_toks_ls_l():
    exp = '![ls -l]'
    obs = subproc_toks('ls -l', lexer=LEXER, returnline=True)
    assert_equal(exp, obs)


def test_subproc_toks_git():
    s = 'git commit -am "hello doc"'
    exp = '![{0}]'.format(s)
    obs = subproc_toks(s, lexer=LEXER, returnline=True)
    assert_equal(exp, obs)


def test_subproc_toks_git_semi():
    s = 'git commit -am "hello doc"'
    exp = '![{0}];'.format(s)
    obs = subproc_toks(s + ';', lexer=LEXER, returnline=True)
    assert_equal(exp, obs)


def test_subproc_toks_git_nl():
    s = 'git commit -am "hello doc"'
    exp = '![{0}]\n'.format(s)
    obs = subproc_toks(s + '\n', lexer=LEXER, returnline=True)
    assert_equal(exp, obs)


def test_subproc_toks_indent_ls():
    s = 'ls -l'
    exp = INDENT + '![{0}]'.format(s)
    obs = subproc_toks(INDENT + s, mincol=len(INDENT), lexer=LEXER,
                       returnline=True)
    assert_equal(exp, obs)


def test_subproc_toks_indent_ls_nl():
    s = 'ls -l'
    exp = INDENT + '![{0}]\n'.format(s)
    obs = subproc_toks(INDENT + s + '\n', mincol=len(INDENT), lexer=LEXER,
                       returnline=True)
    assert_equal(exp, obs)


def test_subproc_toks_indent_ls_no_min():
    s = 'ls -l'
    exp = INDENT + '![{0}]'.format(s)
    obs = subproc_toks(INDENT + s, lexer=LEXER, returnline=True)
    assert_equal(exp, obs)


def test_subproc_toks_indent_ls_no_min_nl():
    s = 'ls -l'
    exp = INDENT + '![{0}]\n'.format(s)
    obs = subproc_toks(INDENT + s + '\n', lexer=LEXER, returnline=True)
    assert_equal(exp, obs)


def test_subproc_toks_indent_ls_no_min_semi():
    s = 'ls'
    exp = INDENT + '![{0}];'.format(s)
    obs = subproc_toks(INDENT + s + ';', lexer=LEXER, returnline=True)
    assert_equal(exp, obs)


def test_subproc_toks_indent_ls_no_min_semi_nl():
    s = 'ls'
    exp = INDENT + '![{0}];\n'.format(s)
    obs = subproc_toks(INDENT + s + ';\n', lexer=LEXER, returnline=True)
    assert_equal(exp, obs)


def test_subproc_toks_ls_comment():
    s = 'ls -l'
    com = '  # lets list'
    exp = '![{0}]{1}'.format(s, com)
    obs = subproc_toks(s + com, lexer=LEXER, returnline=True)
    assert_equal(exp, obs)


def test_subproc_toks_ls_42_comment():
    s = 'ls 42'
    com = '  # lets list'
    exp = '![{0}]{1}'.format(s, com)
    obs = subproc_toks(s + com, lexer=LEXER, returnline=True)
    assert_equal(exp, obs)


def test_subproc_toks_ls_str_comment():
    s = 'ls "wakka"'
    com = '  # lets list'
    exp = '![{0}]{1}'.format(s, com)
    obs = subproc_toks(s + com, lexer=LEXER, returnline=True)
    assert_equal(exp, obs)


def test_subproc_toks_indent_ls_comment():
    ind = '    '
    s = 'ls -l'
    com = '  # lets list'
    exp = '{0}![{1}]{2}'.format(ind, s, com)
    obs = subproc_toks(ind + s + com, lexer=LEXER, returnline=True)
    assert_equal(exp, obs)


def test_subproc_toks_indent_ls_str():
    ind = '    '
    s = 'ls "wakka"'
    com = '  # lets list'
    exp = '{0}![{1}]{2}'.format(ind, s, com)
    obs = subproc_toks(ind + s + com, lexer=LEXER, returnline=True)
    assert_equal(exp, obs)


def test_subproc_toks_ls_l_semi_ls_first():
    lsdl = 'ls -l'
    ls = 'ls'
    s = '{0}; {1}'.format(lsdl, ls)
    exp = '![{0}]; {1}'.format(lsdl, ls)
    obs = subproc_toks(s, lexer=LEXER, maxcol=6, returnline=True)
    assert_equal(exp, obs)


def test_subproc_toks_ls_l_semi_ls_second():
    lsdl = 'ls -l'
    ls = 'ls'
    s = '{0}; {1}'.format(lsdl, ls)
    exp = '{0}; ![{1}]'.format(lsdl, ls)
    obs = subproc_toks(s, lexer=LEXER, mincol=7, returnline=True)
    assert_equal(exp, obs)


def test_subproc_toks_hello_mom_first():
    fst = "echo 'hello'"
    sec = "echo 'mom'"
    s = '{0}; {1}'.format(fst, sec)
    exp = '![{0}]; {1}'.format(fst, sec)
    obs = subproc_toks(s, lexer=LEXER, maxcol=len(fst)+1, returnline=True)
    assert_equal(exp, obs)


def test_subproc_toks_hello_mom_second():
    fst = "echo 'hello'"
    sec = "echo 'mom'"
    s = '{0}; {1}'.format(fst, sec)
    exp = '{0}; ![{1}]'.format(fst, sec)
    obs = subproc_toks(s, lexer=LEXER, mincol=len(fst), returnline=True)
    assert_equal(exp, obs)


def test_subproc_toks_comment():
    exp = None
    obs = subproc_toks('# I am a comment', lexer=LEXER, returnline=True)
    assert_equal(exp, obs)


def test_subproc_toks_not():
    exp = 'not ![echo mom]'
    obs = subproc_toks('not echo mom', lexer=LEXER, returnline=True)
    assert_equal(exp, obs)


def test_subproc_toks_paren():
    exp = '(![echo mom])'
    obs = subproc_toks('(echo mom)', lexer=LEXER, returnline=True)
    assert_equal(exp, obs)


def test_subproc_toks_paren_ws():
    exp = '(![echo mom])  '
    obs = subproc_toks('(echo mom)  ', lexer=LEXER, returnline=True)
    assert_equal(exp, obs)


def test_subproc_toks_not_paren():
    exp = 'not (![echo mom])'
    obs = subproc_toks('not (echo mom)', lexer=LEXER, returnline=True)
    assert_equal(exp, obs)


def test_subproc_toks_and_paren():
    exp = 'True and (![echo mom])'
    obs = subproc_toks('True and (echo mom)', lexer=LEXER, returnline=True)
    assert_equal(exp, obs)


def test_subproc_toks_paren_and_paren():
    exp = '(![echo a]) and (echo b)'
    obs = subproc_toks('(echo a) and (echo b)', maxcol=9, lexer=LEXER, returnline=True)
    assert_equal(exp, obs)


def test_subproc_toks_semicolon_only():
    exp = None
    obs = subproc_toks(';', lexer=LEXER, returnline=True)
    assert_equal(exp, obs)


def test_subproc_toks_pyeval():
    s = 'echo @(1+1)'
    exp = '![{0}]'.format(s)
    obs = subproc_toks(s, lexer=LEXER, returnline=True)
    assert_equal(exp, obs)


def test_subproc_toks_twopyeval():
    s = 'echo @(1+1) @(40 + 2)'
    exp = '![{0}]'.format(s)
    obs = subproc_toks(s, lexer=LEXER, returnline=True)
    assert_equal(exp, obs)


def test_subproc_toks_pyeval_parens():
    s = 'echo @(1+1)'
    inp = '({0})'.format(s)
    exp = '(![{0}])'.format(s)
    obs = subproc_toks(inp, lexer=LEXER, returnline=True)
    assert_equal(exp, obs)


def test_subproc_toks_twopyeval_parens():
    s = 'echo @(1+1) @(40+2)'
    inp = '({0})'.format(s)
    exp = '(![{0}])'.format(s)
    obs = subproc_toks(inp, lexer=LEXER, returnline=True)
    assert_equal(exp, obs)


def test_subproc_toks_pyeval_nested():
    s = 'echo @(min(1, 42))'
    exp = '![{0}]'.format(s)
    obs = subproc_toks(s, lexer=LEXER, returnline=True)
    assert_equal(exp, obs)


def test_subproc_toks_pyeval_nested_parens():
    s = 'echo @(min(1, 42))'
    inp = '({0})'.format(s)
    exp = '(![{0}])'.format(s)
    obs = subproc_toks(inp, lexer=LEXER, returnline=True)
    assert_equal(exp, obs)


def test_subproc_toks_capstdout():
    s = 'echo $(echo bat)'
    exp = '![{0}]'.format(s)
    obs = subproc_toks(s, lexer=LEXER, returnline=True)
    assert_equal(exp, obs)


def test_subproc_toks_capproc():
    s = 'echo !(echo bat)'
    exp = '![{0}]'.format(s)
    obs = subproc_toks(s, lexer=LEXER, returnline=True)
    assert_equal(exp, obs)


def test_subproc_toks_pyeval_redirect():
    s = 'echo @("foo") > bar'
    inp = '{0}'.format(s)
    exp = '![{0}]'.format(s)
    obs = subproc_toks(inp, lexer=LEXER, returnline=True)
    assert_equal(exp, obs)


def test_subexpr_from_unbalanced_parens():
    cases = [
        ('f(x.', 'x.'),
        ('f(1,x.', 'x.'),
        ('f((1,10),x.y', 'x.y'),
        ]
    for expr, exp in cases:
        obs = subexpr_from_unbalanced(expr, '(', ')')
        yield assert_equal, exp, obs

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
        yield assert_equal, exp, obs


def test_is_int():
    yield assert_true, is_int(42)
    yield assert_false, is_int('42')


def test_is_float():
    yield assert_true, is_float(42.0)
    yield assert_false, is_float('42.0')


def test_is_string():
    yield assert_true, is_string('42.0')
    yield assert_false, is_string(42.0)


def test_is_callable():
    yield assert_true, is_callable(lambda: 42.0)
    yield assert_false, is_callable(42.0)


def test_is_string_or_callable():
    yield assert_true, is_string_or_callable('42.0')
    yield assert_true, is_string_or_callable(lambda: 42.0)
    yield assert_false, is_string(42.0)


def test_always_true():
    yield assert_true, always_true(42)
    yield assert_true, always_true('42')


def test_always_false():
    yield assert_false, always_false(42)
    yield assert_false, always_false('42')


def test_ensure_string():
    cases = [
        (42, '42'),
        ('42', '42'),
        ]
    for inp, exp in cases:
        obs = ensure_string(inp)
        yield assert_equal, exp, obs


def test_is_env_path():
    cases = [
        ('/home/wakka', False),
        (['/home/jawaka'], True),
        ]
    for inp, exp in cases:
        obs = is_env_path(inp)
        yield assert_equal, exp, obs


def test_str_to_env_path():
    cases = [
        ('/home/wakka', ['/home/wakka']),
        ('/home/wakka' + os.pathsep + '/home/jawaka',
         ['/home/wakka', '/home/jawaka']),
        ]
    for inp, exp in cases:
        obs = str_to_env_path(inp)
        yield assert_equal, exp, obs


def test_env_path_to_str():
    cases = [
        (['/home/wakka'], '/home/wakka'),
        (['/home/wakka', '/home/jawaka'],
         '/home/wakka' + os.pathsep + '/home/jawaka'),
        ]
    for inp, exp in cases:
        obs = env_path_to_str(inp)
        yield assert_equal, exp, obs


def test_is_bool():
    yield assert_equal, True, is_bool(True)
    yield assert_equal, True, is_bool(False)
    yield assert_equal, False, is_bool(1)
    yield assert_equal, False, is_bool('yooo hooo!')


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
        yield assert_equal, exp, obs


def test_bool_to_str():
    yield assert_equal, '1', bool_to_str(True)
    yield assert_equal, '', bool_to_str(False)


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
        yield assert_equal, exp, obs


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
        yield assert_equal, exp, obs


def test_bool_or_int_to_str():
    cases = [
        (True, '1'),
        (False, ''),
        (1, '1'),
        (0, '0'),
        ]
    for inp, exp in cases:
        obs = bool_or_int_to_str(inp)
        yield assert_equal, exp, obs


def test_ensure_int_or_slice():
    cases = [
        (42, 42),
        (None, slice(None, None, None)),
        ('42', 42),
        ('-42', -42),
        ('1:2:3', slice(1, 2, 3)),
        ('1::3', slice(1, None, 3)),
        ('1:', slice(1, None, None)),
        ('[1:2:3]', slice(1, 2, 3)),
        ('(1:2:3)', slice(1, 2, 3)),
        ]
    for inp, exp in cases:
        obs = ensure_int_or_slice(inp)
        yield assert_equal, exp, obs


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
        yield assert_equal, exp, obs


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
        yield assert_equal, exp, obs


def test_dynamic_cwd_tuple_to_str():
    cases = [
        ((20.0, 'c'), '20.0'),
        ((20.0, '%'), '20.0%'),
        ((float('inf'), 'c'), 'inf'),
        ]
    for inp, exp in cases:
        obs = dynamic_cwd_tuple_to_str(inp)
        yield assert_equal, exp, obs


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
        yield assert_equal, esc, obs


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
        yield assert_equal, esc, obs


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
    yield assert_equal, check_for_partial_string('no strings here'), (None, None, None)
    yield assert_equal, check_for_partial_string(''), (None, None, None)
    for s, e in _startend.items():
        _test = s + inners + e
        for l in _leaders:
            for f in _leaders:
                # single string
                _res = check_for_partial_string(l + _test + f)
                yield assert_equal, _res, (len(l), len(l) + len(_test), s)
                # single partial
                _res = check_for_partial_string(l + f + s + inners)
                yield assert_equal, _res, (len(l+f), None, s)
                for s2, e2 in _startend.items():
                    _test2 = s2 + inners + e2
                    for l2 in _leaders:
                        for f2 in _leaders:
                            # two strings
                            _res = check_for_partial_string(l + _test + f + l2 + _test2 + f2)
                            yield assert_equal, _res, (len(l+_test+f+l2), len(l+_test+f+l2+_test2), s2)
                            # one string, one partial
                            _res = check_for_partial_string(l + _test + f + l2 + s2 + inners)
                            yield assert_equal, _res, (len(l+_test+f+l2), None, s2)


def test_executables_in():


    expected = set()
    types = ('file', 'directory', 'brokensymlink')
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
                    with open(tmp_path,'w') as f:
                        f.write('deleteme')
                        os.symlink(tmp_path, path)
                    os.remove(tmp_path)
                if executable and not _type == 'brokensymlink' :
                    os.chmod(path, stat.S_IXUSR | stat.S_IRUSR | stat.S_IWUSR)
            result = set(executables_in(test_path))
    assert_equal(expected, result)


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
        yield assert_equal, exp, obs

if __name__ == '__main__':
    nose.runmodule()
