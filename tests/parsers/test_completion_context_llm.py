"""Regression tests for hash-seed independence of the completion grammar."""

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("seed", ["1", "123"])
def test_grammar_independent_of_hash_seed(seed):
    root = Path(__file__).resolve().parents[2]
    # PLY numbers productions in grammar order, so set iteration order must
    # not reach the token tuple or the generated rule docstrings.
    script = """
from xonsh.parsers.completion_context import CompletionContextParser as P

rule = P.p_multiple_commands_many.__doc__
assert rule == (
    "commands : "
    + "\\n\\t| ".join(f"commands {t} command" for t in sorted(P.multi_tokens))
), rule
args = P.p_any_token_arg.__doc__.split(" : ", 1)[1].split("\\n\\t| ")
assert args == sorted(args), args
tokens = P().tokens
assert list(tokens) == sorted(tokens), tokens
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=root,
        env=dict(os.environ, PYTHONHASHSEED=seed),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
