"""Shared fixtures for parser tests."""

import ast

import pytest

from xonsh.parser import Parser
from xonsh.pytest.tools import nodes_equal


@pytest.fixture(scope="module")
def parser():
    return Parser(yacc_optimize=False, yacc_debug=True)


@pytest.fixture
def xsh(xession, monkeypatch, parser):
    monkeypatch.setattr(xession.execer, "parser", parser)
    return xession


@pytest.fixture
def check_ast(parser, xsh):
    def factory(inp, run=True, mode="eval", debug_level=0):
        __tracebackhide__ = True
        # expect a Python AST
        exp = ast.parse(inp, mode=mode)
        # observe something from xonsh
        obs = parser.parse(inp, debug_level=debug_level)
        # Check that they are equal
        assert nodes_equal(exp, obs)
        # round trip by running xonsh AST via Python
        if run:
            exec(compile(obs, "<test-ast>", mode))

    return factory


@pytest.fixture
def check_stmts(check_ast):
    def factory(inp, run=True, mode="exec", debug_level=0):
        __tracebackhide__ = True
        if not inp.endswith("\n"):
            inp += "\n"
        check_ast(inp, run=run, mode=mode, debug_level=debug_level)

    return factory


@pytest.fixture
def check_xonsh_ast(xsh, parser):
    def factory(
        xenv,
        inp,
        run=True,
        mode="eval",
        debug_level=0,
        return_obs=False,
        globals=None,
        locals=None,
    ):
        xsh.env.update(xenv)
        obs = parser.parse(inp, debug_level=debug_level)
        if obs is None:
            return  # comment only
        bytecode = compile(obs, "<test-xonsh-ast>", mode)
        if run:
            exec(bytecode, globals, locals)
        return obs if return_obs else True

    return factory
