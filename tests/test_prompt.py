import os
import subprocess as sp
import tempfile
from unittest.mock import Mock

import pytest

from xonsh.environ import Env
from xonsh.prompt.base import PromptFormatter, PROMPT_FIELDS
from xonsh.prompt import vc

from tools import DummyEnv


@pytest.fixture
def formatter(xonsh_builtins):
    return PromptFormatter()


@pytest.fixture
def live_fields():
    return PROMPT_FIELDS


@pytest.mark.parametrize(
    "fields", [{"a_string": "cat", "none": (lambda: None), "f": (lambda: "wakka")}]
)
@pytest.mark.parametrize(
    "inp, exp",
    [
        ("my {a_string}", "my cat"),
        ("my {none}{a_string}", "my cat"),
        ("{f} jawaka", "wakka jawaka"),
    ],
)
def test_format_prompt(inp, exp, fields, formatter):
    obs = formatter(template=inp, fields=fields)
    assert exp == obs


@pytest.mark.parametrize(
    "fields",
    [
        {
            "a_string": "cats",
            "a_number": 7,
            "empty": "",
            "current_job": (lambda: "sleep"),
            "none": (lambda: None),
        }
    ],
)
@pytest.mark.parametrize(
    "inp, exp",
    [
        ("{a_number:{0:^3}}cats", " 7 cats"),
        ("{current_job:{} | }xonsh", "sleep | xonsh"),
        ("{none:{} | }{a_string}{empty:!}", "cats!"),
        ("{none:{}}", ""),
        ("{{{a_string:{{{}}}}}}", "{{cats}}"),
        ("{{{none:{{{}}}}}}", "{}"),
    ],
)
def test_format_prompt_with_format_spec(inp, exp, fields, formatter):
    obs = formatter(template=inp, fields=fields)
    assert exp == obs


def test_format_prompt_with_broken_template(formatter):
    for p in ("{user", "{user}{hostname"):
        assert formatter(p) == p

    # '{{user' will be parsed to '{user'
    for p in ("{{user}", "{{user"):
        assert "user" in formatter(p)


@pytest.mark.parametrize("inp", ["{user", "{{user", "{{user}", "{user}{hostname"])
def test_format_prompt_with_broken_template_in_func(inp, formatter):
    # '{{user' will be parsed to '{user'
    assert "{user" in formatter(lambda: inp)


def test_format_prompt_with_invalid_func(formatter, xonsh_builtins):
    xonsh_builtins.__xonsh__.env = Env()

    def p():
        foo = bar  # raises exception # noqa
        return "{user}"

    assert isinstance(formatter(p), str)


def test_format_prompt_with_func_that_raises(formatter, capsys, xonsh_builtins):
    xonsh_builtins.__xonsh__.env = Env()
    template = "tt {zerodiv} tt"
    exp = "tt {BACKGROUND_RED}{ERROR:zerodiv}{NO_COLOR} tt"
    fields = {"zerodiv": lambda: 1 / 0}
    obs = formatter(template, fields)
    assert exp == obs
    out, err = capsys.readouterr()
    assert "prompt: error" in err


def test_format_prompt_with_no_env(formatter, xonsh_builtins, live_fields):
    xonsh_builtins.__xonsh__.shell.prompt_formatter = formatter

    env = Env()
    env.pop("VIRTUAL_ENV", None)  # For virtualenv
    env.pop("CONDA_DEFAULT_ENV", None)  # For conda/CircleCI
    xonsh_builtins.__xonsh__.env = env

    assert formatter("{env_name}", fields=live_fields) == ""


@pytest.mark.parametrize("envname", ["env", "foo", "bar"])
def test_format_prompt_with_various_envs(
    formatter, xonsh_builtins, live_fields, envname
):
    xonsh_builtins.__xonsh__.shell.prompt_formatter = formatter

    env = Env(VIRTUAL_ENV=envname)
    xonsh_builtins.__xonsh__.env = env

    exp = live_fields["env_prefix"] + envname + live_fields["env_postfix"]
    assert formatter("{env_name}", fields=live_fields) == exp


@pytest.mark.parametrize("pre", ["(", "[[", "", "   "])
@pytest.mark.parametrize("post", [")", "]]", "", "   "])
def test_format_prompt_with_various_prepost(
    formatter, xonsh_builtins, live_fields, pre, post
):
    xonsh_builtins.__xonsh__.shell.prompt_formatter = formatter

    env = Env(VIRTUAL_ENV="env")
    xonsh_builtins.__xonsh__.env = env

    live_fields.update({"env_prefix": pre, "env_postfix": post})

    exp = pre + "env" + post
    assert formatter("{env_name}", fields=live_fields) == exp


def test_noenv_with_disable_set(formatter, xonsh_builtins, live_fields):
    xonsh_builtins.__xonsh__.shell.prompt_formatter = formatter

    env = Env(VIRTUAL_ENV="env", VIRTUAL_ENV_DISABLE_PROMPT=1)
    xonsh_builtins.__xonsh__.env = env

    exp = ""
    assert formatter("{env_name}", fields=live_fields) == exp


@pytest.mark.parametrize("disable", [0, 1])
def test_custom_env_overrides_default(formatter, xonsh_builtins, live_fields, disable):
    xonsh_builtins.__xonsh__.shell.prompt_formatter = formatter

    prompt = "!venv active! "

    env = Env(
        VIRTUAL_ENV="env", VIRTUAL_ENV_PROMPT=prompt, VIRTUAL_ENV_DISABLE_PROMPT=disable
    )
    xonsh_builtins.__xonsh__.env = env

    exp = "" if disable else prompt
    assert formatter("{env_name}", fields=live_fields) == exp


def test_promptformatter_cache(formatter):
    spam = Mock()
    template = "{spam} and {spam}"
    fields = {"spam": spam}

    formatter(template, fields)

    assert spam.call_count == 1


def test_promptformatter_clears_cache(formatter):
    spam = Mock()
    template = "{spam} and {spam}"
    fields = {"spam": spam}

    formatter(template, fields)
    formatter(template, fields)

    assert spam.call_count == 2


# Xonsh interaction with version control systems.
VC_BRANCH = {"git": "master", "hg": "default"}


@pytest.fixture(scope="module", params=VC_BRANCH.keys())
def test_repo(request):
    """Return a dict with vc and a temporary dir
    that is a repository for testing.
    """
    vc = request.param
    temp_dir = tempfile.mkdtemp()
    os.chdir(temp_dir)
    try:
        sp.call([vc, "init"])
    except FileNotFoundError:
        pytest.skip("cannot find {} executable".format(vc))
    # git needs at least one commit
    if vc == "git":
        with open("test-file", "w"):
            pass
        sp.call(["git", "add", "test-file"])
        sp.call(["git", "commit", "--no-gpg-sign", "-m", "test commit"])
    return {"name": vc, "dir": temp_dir}


def test_test_repo(test_repo):
    dotdir = os.path.isdir(
        os.path.join(test_repo["dir"], ".{}".format(test_repo["name"]))
    )
    assert dotdir
    if test_repo["name"] == "git":
        assert os.path.isfile(os.path.join(test_repo["dir"], "test-file"))


def test_no_repo(xonsh_builtins):
    import queue

    temp_dir = tempfile.mkdtemp()
    xonsh_builtins.__xonsh__.env = Env(VC_BRANCH_TIMEOUT=2, PWD=temp_dir)
    q = queue.Queue()
    try:
        vc._get_hg_root(q)
    except AttributeError:
        assert False


def test_vc_get_branch(test_repo, xonsh_builtins):
    xonsh_builtins.__xonsh__.env = Env(VC_BRANCH_TIMEOUT=2)
    # get corresponding function from vc module
    fun = "get_{}_branch".format(test_repo["name"])
    obs = getattr(vc, fun)()
    if obs is not None:
        assert obs == VC_BRANCH[test_repo["name"]]


def test_current_branch_calls_locate_binary_for_empty_cmds_cache(xonsh_builtins):
    cache = xonsh_builtins.__xonsh__.commands_cache
    xonsh_builtins.__xonsh__.env = DummyEnv(VC_BRANCH_TIMEOUT=1)
    cache.is_empty = Mock(return_value=True)
    cache.locate_binary = Mock(return_value="")
    vc.current_branch()
    assert cache.locate_binary.called


def test_current_branch_does_not_call_locate_binary_for_non_empty_cmds_cache(
    xonsh_builtins
):
    cache = xonsh_builtins.__xonsh__.commands_cache
    xonsh_builtins.__xonsh__.env = DummyEnv(VC_BRANCH_TIMEOUT=1)
    cache.is_empty = Mock(return_value=False)
    cache.locate_binary = Mock(return_value="")
    # make lazy locate return nothing to avoid running vc binaries
    cache.lazy_locate_binary = Mock(return_value="")
    vc.current_branch()
    assert not cache.locate_binary.called
