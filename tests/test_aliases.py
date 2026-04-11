"""Testing built_ins.Aliases"""

import inspect
import os
import sys

import pytest

from xonsh.aliases import (
    Aliases,
    ExecAlias,
    get_xxonsh_alias,
    run_alias_by_params,
)


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
    monkeypatch.setitem(xonsh_session.env, "XONSH_SUBPROC_CMD_RAISE_ERROR", False)
    # Also disable the chain-result raise so a non-zero `python -c "exit(N)"`
    # surfaces as the alias's return value instead of an exception.
    monkeypatch.setitem(xonsh_session.env, "XONSH_SUBPROC_RAISE_ERROR", False)
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


def test_register_click_command(xession):
    """Basic smoke test for the click integration."""
    import io

    click = pytest.importorskip("click")

    aliases = Aliases()

    @aliases.register_click_command
    @aliases.click.option("--name", default="World")
    def _greet(ctx, name):
        ctx.click.echo(f"hello {name}", file=ctx.stdout)

    # Decorator derives the alias name from the function (leading underscore
    # stripped) and exposes the click module both on ``aliases`` and ``ctx``.
    assert "greet" in aliases
    assert aliases.click is click

    # Invoking the alias runs the click command, which writes to ctx.stdout.
    stdout = io.StringIO()
    aliases["greet"](args=["--name", "Xonsh"], stdout=stdout)
    assert stdout.getvalue() == "hello Xonsh\n"


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


def test_env_overlay_shadows_global(xession):
    """env overlay has priority over global env for reads."""
    xession.env["X"] = "global"
    alias_env = {}
    with xession.env.swap(overlay=alias_env):
        alias_env["X"] = "local"
        assert xession.env["X"] == "local"
    assert xession.env["X"] == "global"


def test_env_overlay_global_write_persists(xession):
    """Direct writes to env persist after overlay is removed."""
    alias_env = {}
    with xession.env.swap(overlay=alias_env):
        alias_env["LOCAL"] = 1
        xession.env["GLOBAL"] = 2
    assert "LOCAL" not in xession.env
    assert xession.env["GLOBAL"] == 2


def test_env_overlay_visible_in_detype(xession):
    """Overlay values are included in detype() for subprocesses."""
    alias_env = {}
    with xession.env.swap(overlay=alias_env):
        alias_env["MY_VAR"] = "from_overlay"
        detyped = xession.env.detype()
        assert detyped["MY_VAR"] == "from_overlay"


def test_env_overlay_thread_isolation(xession):
    """Overlay in one thread is not visible in another."""
    from threading import Thread

    alias_env = {"THREAD_VAR": "yes"}
    visible_in_other = []

    def check():
        visible_in_other.append("THREAD_VAR" in xession.env)

    with xession.env.swap(overlay=alias_env):
        t = Thread(target=check)
        t.start()
        t.join()
        assert xession.env["THREAD_VAR"] == "yes"

    assert visible_in_other == [False]


@pytest.mark.parametrize(
    "argv0",
    [
        "/usr/local/bin/xonsh",
        "/opt/env/bin/xonsh",
        "xonsh",
    ],
)
def test_get_xxonsh_alias_entrypoint_returns_single_element_list(monkeypatch, argv0):
    """When launched via an entry point, the alias is ``[sys.argv[0]]``.

    The result is always a list so that callers can concatenate it with
    other argv lists without having to special-case the string form.
    """
    monkeypatch.setattr(sys, "argv", [argv0])
    assert get_xxonsh_alias() == [argv0]


def test_get_xxonsh_alias_from_source_returns_bootstrap_list(monkeypatch, tmp_path):
    """
    When launched via ``python -m xonsh``, the alias must NOT be a plain
    ``[python, -m, xonsh]``: that would be CWD-dependent and could silently
    resolve to a different xonsh (site-packages, namespace stub, or error)
    depending on where the user happens to be.

    Instead the alias must be a ``[python, -c, bootstrap]`` list where the
    bootstrap prepends the parent of the source ``xonsh`` package to
    ``sys.path`` and then runs ``xonsh.main.main()``.
    """
    fake_src_root = tmp_path / "repo"
    fake_pkg = fake_src_root / "xonsh"
    fake_pkg.mkdir(parents=True)
    fake_main = fake_pkg / "__main__.py"
    fake_main.write_text("")  # only the basename matters for detection

    monkeypatch.setattr(sys, "argv", [str(fake_main)])
    monkeypatch.setattr(sys, "executable", "/fake/python")

    alias = get_xxonsh_alias()

    assert isinstance(alias, list)
    assert len(alias) == 3
    assert alias[0] == "/fake/python"
    assert alias[1] == "-c"
    bootstrap = alias[2]
    assert "from xonsh.main import main" in bootstrap
    assert "main()" in bootstrap
    # The parent of the xonsh/ package dir must be prepended to sys.path
    # so that ``import xonsh`` resolves to the source tree, not whatever
    # is currently installed or happens to be in CWD.
    assert repr(str(fake_src_root)) in bootstrap
    assert "sys.path.insert(0" in bootstrap


def test_get_xxonsh_alias_source_handles_relative_argv0(monkeypatch, tmp_path):
    """Relative ``sys.argv[0]`` must be resolved against the real CWD."""
    fake_src_root = tmp_path / "repo"
    fake_pkg = fake_src_root / "xonsh"
    fake_pkg.mkdir(parents=True)
    (fake_pkg / "__main__.py").write_text("")

    # Simulate a launch recorded as a relative path
    monkeypatch.chdir(fake_src_root)
    monkeypatch.setattr(sys, "argv", ["xonsh/__main__.py"])
    monkeypatch.setattr(sys, "executable", "/fake/python")

    alias = get_xxonsh_alias()
    bootstrap = alias[2]
    # pkg_parent must be the absolute path, not a relative string
    assert repr(str(fake_src_root)) in bootstrap


def test_get_xxonsh_alias_source_bootstrap_runs_from_any_cwd(monkeypatch, tmp_path):
    """
    End-to-end: the bootstrap command must actually launch the source
    xonsh from a CWD that contains no ``xonsh/`` package.
    """
    import pathlib
    import subprocess

    # Resolve the real xonsh source repo from this test file's location
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    real_main = repo_root / "xonsh" / "__main__.py"
    assert real_main.is_file(), f"expected xonsh/__main__.py at {real_main}"

    # Pretend the current session was launched via python -m xonsh
    monkeypatch.setattr(sys, "argv", [str(real_main)])

    cmd = get_xxonsh_alias()
    assert isinstance(cmd, list)

    # Ensure tmp_path truly does not look like a xonsh source tree
    assert not (tmp_path / "xonsh").exists()

    result = subprocess.run(
        [*cmd, "--no-rc", "-c", "import xonsh; print(xonsh.__file__)"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        timeout=60,
    )
    assert result.returncode == 0, (
        f"returncode={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    expected_path = str(repo_root / "xonsh" / "__init__.py")
    assert expected_path in result.stdout, (
        f"expected {expected_path} in stdout, got:\n{result.stdout}"
    )
