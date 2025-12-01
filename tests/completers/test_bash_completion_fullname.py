import subprocess
from xonsh.completers.bash_completion import bash_completions
from contextlib import contextmanager

def fake_check_output_success(*args, **kwargs):
    return "-F _func\nreload\neload\n"

def test_bash_completion_preserves_full_name(monkeypatch):
    monkeypatch.setattr(subprocess, "check_output", fake_check_output_success)

    prefix = "re"
    line = "re"
    begidx = 0
    endidx = len(line)

    out, lprefix = bash_completions(prefix, line, begidx, endidx, env={}, paths=())

    rendered = {str(c) for c in out}

    assert "reload" in rendered, f"expected 'reload' in completions, got: {rendered}"
