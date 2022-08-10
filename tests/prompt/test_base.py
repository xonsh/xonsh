import functools
from unittest.mock import Mock

import pytest

from xonsh.prompt import env as prompt_env
from xonsh.prompt.base import PromptField, PromptFields, PromptFormatter


@pytest.fixture
def formatter(xession):
    return PromptFormatter()


@pytest.fixture
def live_fields(xession):
    return PromptFields(xession)


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
def test_format_prompt(inp, exp, fields, formatter, xession):
    obs = formatter(template=inp, fields=fields)
    assert exp == obs


@pytest.mark.parametrize(
    "fields",
    [
        {
            "a_string": "cats",
            "a_number": 7,
            "empty": "",
            "a_function": (lambda: "hello"),
            "current_job": PromptField(value="sleep"),
            "none": (lambda: None),
            "none_pf": PromptField(value=None),
        }
    ],
)
@pytest.mark.parametrize(
    "inp, exp",
    [
        ("{a_number:{0:^3}}cats", " 7 cats"),
        ("{a_function:{} | }xonsh", "hello | xonsh"),
        ("{current_job:{} | }xonsh", "sleep | xonsh"),
        ("{none_pf:{} | }xonsh", "xonsh"),
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
    def p():
        foo = bar  # raises exception # noqa
        return "{user}"

    assert isinstance(formatter(p), str)


def test_format_prompt_with_func_that_raises(formatter, capsys, xession):
    template = "tt {zerodiv} tt"
    exp = "tt {BACKGROUND_RED}{ERROR:zerodiv}{RESET} tt"
    fields = {"zerodiv": lambda: 1 / 0}
    obs = formatter(template, fields)
    assert exp == obs
    out, err = capsys.readouterr()
    assert "prompt: error" in err


def test_format_prompt_with_no_env(formatter, xession, live_fields, env):
    xession.shell.prompt_formatter = formatter

    env.pop("VIRTUAL_ENV", None)  # For virtualenv
    env.pop("CONDA_DEFAULT_ENV", None)  # For conda/CircleCI

    assert formatter("{env_name}", fields=live_fields) == ""


@pytest.mark.parametrize("envname", ["env", "foo", "bar"])
def test_format_prompt_with_various_envs(formatter, xession, live_fields, envname):
    xession.shell.prompt_formatter = formatter

    xession.env["VIRTUAL_ENV"] = envname

    exp = live_fields["env_prefix"] + envname + live_fields["env_postfix"]
    assert formatter("{env_name}", fields=live_fields) == exp


@pytest.mark.parametrize("pre", ["(", "[[", "", "   "])
@pytest.mark.parametrize("post", [")", "]]", "", "   "])
def test_format_prompt_with_various_prepost(formatter, xession, live_fields, pre, post):
    xession.shell.prompt_formatter = formatter

    xession.env["VIRTUAL_ENV"] = "env"

    lf_copy = dict(live_fields)  # live_fields fixture is not idempotent!
    lf_copy.update({"env_prefix": pre, "env_postfix": post})
    exp = pre + "env" + post
    assert formatter("{env_name}", fields=lf_copy) == exp


def test_noenv_with_disable_set(formatter, xession, live_fields):
    xession.shell.prompt_formatter = formatter
    xession.env.update(dict(VIRTUAL_ENV="env", VIRTUAL_ENV_DISABLE_PROMPT=1))

    exp = ""
    assert formatter("{env_name}", fields=live_fields) == exp


class TestPromptFromVenvCfg:
    WANTED = "wanted"
    CONFIGS = [
        f"prompt = '{WANTED}'",
        f'prompt = "{WANTED}"',
        f'\t prompt =  "{WANTED}"   ',
        f"prompt \t=    {WANTED}   ",
        "nothing = here",
    ]
    CONFIGS.extend([f"other = fluff\n{t}\nmore = fluff" for t in CONFIGS])

    @pytest.mark.parametrize("text", CONFIGS)
    def test_determine_env_name_from_cfg(self, monkeypatch, tmp_path, text):
        monkeypatch.setattr(prompt_env, "_surround_env_name", lambda x: x)
        (tmp_path / "pyvenv.cfg").write_text(text)
        wanted = self.WANTED if self.WANTED in text else tmp_path.name
        assert prompt_env._determine_env_name(tmp_path) == wanted


class TestEnvNamePrompt:
    def test_no_prompt(self, formatter, live_fields):
        assert formatter("{env_name}", fields=live_fields) == ""

    def test_search_order(self, monkeypatch, tmp_path, formatter, xession, live_fields):
        xession.shell.prompt_formatter = formatter

        first = "first"
        second = "second"
        third = "third"
        fourth = "fourth"

        pyvenv_cfg = tmp_path / third / "pyvenv.cfg"
        pyvenv_cfg.parent.mkdir()
        pyvenv_cfg.write_text(f"prompt={second}")

        fmt = functools.partial(formatter, "{env_name}", fields=live_fields)
        xession.env.update(
            dict(
                VIRTUAL_ENV_PROMPT=first,
                VIRTUAL_ENV=str(pyvenv_cfg.parent),
                CONDA_DEFAULT_ENV=fourth,
            )
        )

        xession.env["VIRTUAL_ENV_DISABLE_PROMPT"] = 0
        assert fmt() == first

        live_fields.reset()
        xession.env["VIRTUAL_ENV_DISABLE_PROMPT"] = 1
        assert fmt() == ""

        live_fields.reset()
        del xession.env["VIRTUAL_ENV_PROMPT"]
        xession.env["VIRTUAL_ENV_DISABLE_PROMPT"] = 0
        assert fmt() == f"({second}) "

        live_fields.reset()
        xession.env["VIRTUAL_ENV_DISABLE_PROMPT"] = 1
        assert fmt() == ""

        live_fields.reset()
        xession.env["VIRTUAL_ENV_DISABLE_PROMPT"] = 0
        pyvenv_cfg.unlink()
        # In the interest of speed the calls are cached, but if the user
        # fiddles with environments this will bite them. I will not do anythin
        prompt_env._determine_env_name.cache_clear()
        assert fmt() == f"({third}) "

        live_fields.reset()
        xession.env["VIRTUAL_ENV_DISABLE_PROMPT"] = 1
        assert fmt() == ""

        live_fields.reset()
        xession.env["VIRTUAL_ENV_DISABLE_PROMPT"] = 0
        del xession.env["VIRTUAL_ENV"]
        assert fmt() == f"({fourth}) "

        live_fields.reset()
        xession.env["VIRTUAL_ENV_DISABLE_PROMPT"] = 1
        assert fmt() == ""

        live_fields.reset()
        xession.env["VIRTUAL_ENV_DISABLE_PROMPT"] = 0
        del xession.env["CONDA_DEFAULT_ENV"]
        assert fmt() == ""

    @pytest.mark.xfail(reason="caching introduces stale values")
    def test_env_name_updates_on_filesystem_change(self, tmp_path):
        """Due to cache, user might get stale value.

        if user fiddles with env folder or the config, they might get a stale
        value from the cache.
        """
        cfg = tmp_path / "pyvenv.cfg"
        cfg.write_text("prompt=fromfile")
        assert prompt_env._determine_env_name(cfg.parent) == "fromfile"
        cfg.unlink()
        assert prompt_env._determine_env_name(cfg.parent) == cfg.parent.name


@pytest.mark.parametrize("disable", [0, 1])
def test_custom_env_overrides_default(formatter, xession, live_fields, disable):
    xession.shell.prompt_formatter = formatter

    prompt = "!venv active! "

    xession.env.update(
        dict(
            VIRTUAL_ENV="env",
            VIRTUAL_ENV_PROMPT=prompt,
            VIRTUAL_ENV_DISABLE_PROMPT=disable,
        )
    )

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
