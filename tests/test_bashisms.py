"""Tests bashisms xontrib."""
import pytest

@pytest.mark.parametrize('inp, exp', [
    ('x = 42', 'x = 42'),
    ('!!', 'ls'),
    ])
def test_preproc(inp, exp, xonsh_builtins):
    """Test the bash preprocessor."""
    from xontrib.bashisms import bash_preproc
    xonsh_builtins.__xonsh_history__.inps = ['ls\n']
    obs = bash_preproc(inp)
    assert exp == obs