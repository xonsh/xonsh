import pytest

from xonsh.commands_cache import CommandsCache, predict_shell, SHELL_PREDICTOR_PARSER

def test_commands_cache_lazy(xonsh_builtins):
    cc = CommandsCache()
    assert not cc.lazyin('xonsh')
    assert 0 == len(list(cc.lazyiter()))
    assert 0 == cc.lazylen()


TRUE_SHELL_ARGS = [
    ['-c', 'yo'],
    ['-c=yo'],
    ['file'],
    ['-i', '-l', 'file'],
    ['-i', '-c', 'yo'],
    ['-i', 'file'],
    ['-i', '-c', 'yo', 'file'],
    ]

@pytest.mark.parametrize('args', TRUE_SHELL_ARGS)
def test_predict_shell_parser(args):
    ns, unknown = SHELL_PREDICTOR_PARSER.parse_known_args(args)
    if ns.filename is not None:
        assert not ns.filename.startswith('-')


@pytest.mark.parametrize('args', TRUE_SHELL_ARGS)
def test_predict_shell_true(args):
    assert predict_shell(args)


FALSE_SHELL_ARGS = [
    [],
    ['-c'],
    ['-i'],
    ['-i', '-l'],
    ]

@pytest.mark.parametrize('args', FALSE_SHELL_ARGS)
def test_predict_shell_false(args):
    assert not predict_shell(args)

