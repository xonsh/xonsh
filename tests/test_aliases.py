"""Testing built_ins.Aliases"""

import inspect
import os
import sys

import pytest

from xonsh.aliases import Aliases, ExecAlias, run_alias_by_params


def cd(args, stdin=None):
    return args


def make_aliases():
    ales = Aliases(
        {"o": ["omg", "lala"]},
        color_ls=["ls", "--color=true"],
        ls="ls '-  -'",
        cd=cd,
        indirect_cd="cd ..",
    )
    return ales


def test_imports(xession):
    ales = make_aliases()
    expected = {
        "o": ["omg", "lala"],
        "ls": ["ls", "-  -"],
        "color_ls": ["ls", "--color=true"],
        "cd": "FuncAlias",
        "indirect_cd": ["cd", ".."],
    }
    raw = ales._raw
    raw["cd"] = type(ales["cd"]).__name__
    assert raw == expected


def test_eval_normal(xession):
    ales = make_aliases()
    assert ales.get("o") == ["omg", "lala"]


def test_eval_self_reference(xession):
    ales = make_aliases()
    assert ales.get("ls") == ["ls", "-  -"]


def test_eval_recursive(xession):
    ales = make_aliases()
    assert ales.get("color_ls") == ["ls", "-  -", "--color=true"]


def test_eval_callable(xession):
    ales = make_aliases()
    resolved = ales.get(["cd", "tmp"])
    assert callable(resolved[0])
    assert isinstance(resolved[1], str)


def test_eval_recursive_callable_partial(xonsh_execer, xession):
    ales = make_aliases()
    xession.env["HOME"] = os.path.expanduser("~")
    assert ales.get(["indirect_cd", "arg2", "arg3"])[1:] == ["..", "arg2", "arg3"]


def _return_to_sender_all(args, stdin, stdout, stderr, spec, stack):
    return (
        args,
        {
            "stdin": stdin,
            "stdout": stdout,
            "stderr": stderr,
            "spec": spec,
            "stack": stack,
        },
    )


def test_recursive_callable_partial_all(xession):
    ales = Aliases({"rtn": _return_to_sender_all, "rtn-recurse": ["rtn", "arg1"]})
    alias = ales.get("rtn-recurse")[0]
    assert callable(alias)
    args, obs = alias(
        ["arg1", "arg2"], stdin="a", stdout="b", stderr="c", spec="d", stack="e"
    )
    assert args == ["arg1", "arg2"]
    assert len(obs) == 5
    exp = {"stdin": "a", "stdout": "b", "stderr": "c", "spec": "d", "stack": "e"}
    assert obs == exp


def _return_to_sender_handles(args, stdin, stdout, stderr):
    return args, {"stdin": stdin, "stdout": stdout, "stderr": stderr}


def test_recursive_callable_partial_handles(xession):
    ales = Aliases({"rtn": _return_to_sender_handles, "rtn-recurse": ["rtn", "arg1"]})
    alias = ales.get("rtn-recurse")[0]
    assert callable(alias)
    args, obs = alias(["arg1", "arg2"], stdin="a", stdout="b", stderr="c")
    assert args == ["arg1", "arg2"]
    assert len(obs) == 3
    exp = {"stdin": "a", "stdout": "b", "stderr": "c"}
    assert obs == exp


def test_expand_alias():
    ales = Aliases()
    ales["ls"] = ["ls", "-G"]
    ales["ff"] = lambda args: print(args)
    exp_ls = ales.expand_alias("ls ", 3)
    exp_ff = ales.expand_alias("ff ", 3)
    assert exp_ls == "ls -G "
    assert exp_ff == "ff "


def _return_to_sender_none():
    return "wakka", {}


def test_recursive_callable_partial_none(xession):
    ales = Aliases({"rtn": _return_to_sender_none, "rtn-recurse": ["rtn"]})
    alias = ales.get("rtn-recurse")[0]
    assert callable(alias)
    args, obs = alias()
    assert args == "wakka"
    assert len(obs) == 0


@pytest.mark.parametrize(
    "alias",
    [
        "echo 'hi' and echo 'there'",
        "echo 'hi' or echo 'there'",
        "echo 'hi' && echo 'there'",
        "echo 'hi' || echo 'there'",
        "echo 'hi';  echo 'there'",
    ],
)
def test_subprocess_logical_operators(xession, alias):
    ales = make_aliases()
    ales["echocat"] = alias
    assert isinstance(ales["echocat"], ExecAlias)


@pytest.mark.parametrize(
    "alias",
    [
        "echo 'hi' | grep h",
        "echo 'hi' > file",
        "cat < file",
        "COMMAND1 e>o < input.txt | COMMAND2 > output.txt e>> errors.txt",
        "echo 'h|i' | grep h",
        "echo 'h|i << x > 3' | grep x",
    ],
)
def test_subprocess_io_operators(xession, alias):
    ales = make_aliases()
    ales["echocat"] = alias
    assert isinstance(ales["echocat"], ExecAlias)


@pytest.mark.parametrize(
    "alias",
    [
        {"echocat": "ls"},
    ],
)
def test_dict_merging(xession, alias):
    ales = make_aliases()
    assert (ales | alias)["echocat"] == ["ls"]
    assert (alias | ales)["echocat"] == ["ls"]
    assert "echocat" not in ales


@pytest.mark.parametrize(
    "alias",
    [
        {"echocat": "echo Why do people still use python2.7?"},
        {"echocat": "echo Why?"},
    ],
)
def test_dict_merging_assignment(xession, alias):
    ales = make_aliases()
    ales |= alias

    assert "echocat" in ales
    assert " ".join(ales["echocat"]) == alias["echocat"]

    ales = make_aliases()
    alias |= ales

    assert "o" in alias
    assert alias["o"] == ales["o"]


def test_exec_alias_args(xession):
    stack = inspect.stack()
    try:
        ExecAlias("myargs = $args")(["arg0"], stack=stack)
        ExecAlias("myarg0 = $arg0")(["arg0"], stack=stack)
    except KeyError:
        assert False  # noqa

    assert stack[0][0].f_locals["myargs"] == ["arg0"]
    assert stack[0][0].f_locals["myarg0"] == "arg0"


@pytest.mark.parametrize(
    "exp_rtn",
    [0, 1, 2],
)
def test_exec_alias_return_value(exp_rtn, xonsh_session, monkeypatch):
    monkeypatch.setitem(xonsh_session.env, "RAISE_SUBPROC_ERROR", False)
    stack = inspect.stack()
    rtn = ExecAlias(f"{sys.executable} -c 'exit({exp_rtn})'")([], stack=stack)
    assert rtn == exp_rtn


def test_register_decorator(xession):
    aliases = Aliases()

    @aliases.register
    def debug(): ...

    @aliases.register("name")
    def with_options(): ...

    @aliases.register
    def _private(): ...

    assert set(aliases) == {"debug", "name", "private"}


def test_run_alias_by_params():
    def alias_named_params(args, stdout):
        return (args, stdout)

    def alias_named_params_rev(stdout, args):
        return (args, stdout)

    def alias_list_params(a, i, o, e):
        return (a, i, o, e)

    assert run_alias_by_params(alias_named_params, {"args": 1, "stdout": 2}) == (1, 2)
    assert run_alias_by_params(alias_named_params_rev, {"args": 1, "stdout": 2}) == (
        1,
        2,
    )
    assert run_alias_by_params(alias_list_params, {"args": 1, "stderr": 4}) == (
        1,
        None,
        None,
        4,
    )


def test_run_alias_by_params_with_alias():
    """Test that the 'alias' parameter is correctly passed to alias functions."""

    def alias_with_alias_param(alias):
        return alias

    def alias_with_alias_and_args(alias, args):
        return (alias, args)

    def alias_all_params(args, stdin, stdout, stderr, spec, stack, alias):
        return (alias, args)

    # Test with only alias parameter
    assert run_alias_by_params(alias_with_alias_param, {"alias": "myalias"}) == "myalias"

    # Test with alias and args
    assert run_alias_by_params(
        alias_with_alias_and_args, {"alias": "myalias", "args": ["arg1", "arg2"]}
    ) == ("myalias", ["arg1", "arg2"])

    # Test with all parameters including alias
    assert run_alias_by_params(
        alias_all_params,
        {
            "args": ["a1"],
            "stdin": None,
            "stdout": None,
            "stderr": None,
            "spec": None,
            "stack": None,
            "alias": "testalias",
        },
    ) == ("testalias", ["a1"])


def test_callable_alias_with_alias_param(xession):
    """Test that callable aliases can access the alias name via the 'alias' parameter."""

    def alias_func_with_alias(alias):
        return f"Called from: {alias}"

    ales = Aliases({"mycommand": alias_func_with_alias})
    alias = ales.get("mycommand")[0]
    assert callable(alias)

    # The alias should be able to receive the alias parameter
    result = alias([], alias="mycommand")
    assert result == "Called from: mycommand"


def test_recursive_callable_with_alias_param(xession):
    """Test that alias parameter works with recursive aliases."""

    def return_alias_and_args(alias, args):
        return (alias, args)

    ales = Aliases(
        {"base": return_alias_and_args, "recursive": ["base", "prearg"]}
    )
    alias = ales.get("recursive")[0]
    assert callable(alias)

    result = alias(["prearg", "arg2"], alias="recursive")
    assert result == ("recursive", ["prearg", "arg2"])
