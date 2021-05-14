from unittest.mock import Mock

import pytest

from xonsh.environ import Env
from xonsh.prompt.base import PromptFormatter, PROMPT_FIELDS


@pytest.fixture
def formatter(xession):
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


def test_format_prompt_with_invalid_func(formatter, xession):
    xession.env = Env()

    def p():
        foo = bar  # raises exception # noqa
        return "{user}"

    assert isinstance(formatter(p), str)


def test_format_prompt_with_func_that_raises(formatter, capsys, xession):
    xession.env = Env()
    template = "tt {zerodiv} tt"
    exp = "tt {BACKGROUND_RED}{ERROR:zerodiv}{RESET} tt"
    fields = {"zerodiv": lambda: 1 / 0}
    obs = formatter(template, fields)
    assert exp == obs
    out, err = capsys.readouterr()
    assert "prompt: error" in err


def test_format_prompt_with_no_env(formatter, xession, live_fields):
    xession.shell.prompt_formatter = formatter

    env = Env()
    env.pop("VIRTUAL_ENV", None)  # For virtualenv
    env.pop("CONDA_DEFAULT_ENV", None)  # For conda/CircleCI
    xession.env = env

    assert formatter("{env_name}", fields=live_fields) == ""


@pytest.mark.parametrize("envname", ["env", "foo", "bar"])
def test_format_prompt_with_various_envs(formatter, xession, live_fields, envname):
    xession.shell.prompt_formatter = formatter

    env = Env(VIRTUAL_ENV=envname)
    xession.env = env

    exp = live_fields["env_prefix"] + envname + live_fields["env_postfix"]
    assert formatter("{env_name}", fields=live_fields) == exp


@pytest.mark.parametrize("pre", ["(", "[[", "", "   "])
@pytest.mark.parametrize("post", [")", "]]", "", "   "])
def test_format_prompt_with_various_prepost(formatter, xession, live_fields, pre, post):
    xession.shell.prompt_formatter = formatter

    env = Env(VIRTUAL_ENV="env")
    xession.env = env

    live_fields.update({"env_prefix": pre, "env_postfix": post})

    exp = pre + "env" + post
    assert formatter("{env_name}", fields=live_fields) == exp


def test_noenv_with_disable_set(formatter, xession, live_fields):
    xession.shell.prompt_formatter = formatter

    env = Env(VIRTUAL_ENV="env", VIRTUAL_ENV_DISABLE_PROMPT=1)
    xession.env = env

    exp = ""
    assert formatter("{env_name}", fields=live_fields) == exp


@pytest.mark.parametrize("disable", [0, 1])
def test_custom_env_overrides_default(formatter, xession, live_fields, disable):
    xession.shell.prompt_formatter = formatter

    prompt = "!venv active! "

    env = Env(
        VIRTUAL_ENV="env", VIRTUAL_ENV_PROMPT=prompt, VIRTUAL_ENV_DISABLE_PROMPT=disable
    )
    xession.env = env

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
