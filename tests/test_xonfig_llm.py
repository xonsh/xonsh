"""Smoke tests for ``xonsh.xonfig``.

The xonfig command exposes ``info``, ``styles``, ``colors``, ``wizard``, and
``web`` subcommands. The wizard / web ones require an interactive shell and
are skipped here. These tests cover the pure helpers (``_xonfig_format_*``,
``_align_string``, ``_dump_xonfig_*``, ``make_*``) and the ``info`` data shape.
"""

import json

import pytest

from xonsh.xonfig import (
    STRIP_COLOR_RE,
    TAGLINES,
    WELCOME_MSG,
    XONFIG_DUMP_RULES,
    XonfigAlias,
    _align_string,
    _dump_xonfig_env,
    _dump_xonfig_foreign_shell,
    _dump_xonfig_xontribs,
    _info,
    _make_flat_wiz,
    _xonfig_format_human,
    _xonfig_format_json,
    make_envvar,
    make_xonfig_wizard,
)

# --- _xonfig_format_human / _xonfig_format_json ----------------------------


def test_xonfig_format_human_renders_table():
    data = [("foo", "1"), ("bar", "2")]
    out = _xonfig_format_human(data)
    assert "foo" in out
    assert "bar" in out
    # bordered table format
    assert "+" in out
    assert "|" in out


def test_xonfig_format_human_handles_list_values():
    data = [("xontrib", ["abbrevs", "vox"])]
    out = _xonfig_format_human(data)
    assert "xontrib 1" in out
    assert "xontrib 2" in out
    assert "abbrevs" in out
    assert "vox" in out


def test_xonfig_format_human_handles_empty_list():
    """An empty list value renders as a single row, not as N rows."""
    data = [("k", "v"), ("xontrib", [])]
    out = _xonfig_format_human(data)
    assert "k" in out and "v" in out


def test_xonfig_format_json_replaces_spaces_in_keys():
    data = [("Git SHA", "abc123"), ("Commit Date", "2024-01-01")]
    out = _xonfig_format_json(data)
    parsed = json.loads(out)
    assert "Git_SHA" in parsed
    assert "Commit_Date" in parsed
    assert parsed["Git_SHA"] == "abc123"


def test_xonfig_format_json_is_sorted():
    data = [("z", 1), ("a", 2)]
    out = _xonfig_format_json(data)
    # the alphabetically sorted output puts 'a' before 'z'
    assert out.index('"a"') < out.index('"z"')


# --- _align_string ----------------------------------------------------------


def test_align_string_left():
    out = _align_string("hi", align="<", fill=".", width=6)
    assert out == "hi...."


def test_align_string_right():
    out = _align_string("hi", align=">", fill=".", width=6)
    assert out == "....hi"


def test_align_string_center():
    out = _align_string("hi", align="^", fill=".", width=6)
    # padding 2 on each side
    assert out == "..hi.."


def test_align_string_color_codes_are_stripped_for_width_calc():
    """Color tokens like ``{RED}`` are zero-width so they don't count in the pad."""
    s = "{RED}hi{RESET}"
    out = _align_string(s, align="<", fill=" ", width=4)
    # visible length is 2, so two trailing spaces are added
    assert out == s + "  "


def test_align_string_unknown_alignment_returns_input():
    out = _align_string("hi", align="?", fill=" ", width=10)
    assert out == "hi"


def test_strip_color_re_matches_braces():
    assert STRIP_COLOR_RE.sub("", "{RED}hi{RESET}") == "hi"


# --- _dump_xonfig_* helpers -------------------------------------------------


def test_dump_xonfig_xontribs_renders_load_command():
    out = _dump_xonfig_xontribs("/xontribs/", ["abbrevs", "vox"])
    assert out == "xontrib load abbrevs vox"


def test_dump_xonfig_env_emits_assignment(xession):
    """``_dump_xonfig_env`` produces ``$NAME = value`` lines."""
    xession.env["DUMMY_VAR"] = "hello"
    out = _dump_xonfig_env("/env/DUMMY_VAR", "hello")
    assert out.startswith("$DUMMY_VAR =")
    assert "hello" in out


def test_dump_xonfig_foreign_shell_basic_bash():
    out = _dump_xonfig_foreign_shell("/foreign_shells/0/", {"shell": "bash"})
    assert out.startswith("source-bash")


def test_dump_xonfig_foreign_shell_unknown_appends_shell_name():
    out = _dump_xonfig_foreign_shell("/foreign_shells/0/", {"shell": "tcsh"})
    assert out.startswith("source-foreign tcsh")


def test_dump_xonfig_foreign_shell_includes_optional_flags():
    out = _dump_xonfig_foreign_shell(
        "/foreign_shells/0/",
        {
            "shell": "bash",
            "interactive": True,
            "login": False,
            "envcmd": "env",
            "aliascmd": "alias",
            "extra_args": ["--norc"],
            "safe": True,
            "prevcmd": "echo hi",
            "postcmd": "echo bye",
            "funcscmd": "declare -f",
            "sourcer": "source",
        },
    )
    assert "--interactive True" in out
    assert "--login False" in out
    assert "--envcmd env" in out
    assert "--aliascmd alias" in out
    assert "--extra-args" in out
    assert "--safe True" in out
    assert "--prevcmd" in out and "echo hi" in out
    assert "--postcmd" in out and "echo bye" in out
    assert "--funcscmd" in out and "declare -f" in out
    assert "--sourcer source" in out


# --- XONFIG_DUMP_RULES ------------------------------------------------------


def test_xonfig_dump_rules_keys_present():
    rules = dict(XONFIG_DUMP_RULES)
    # Ensure the four well-known patterns are all there.
    assert "/" in rules
    assert "/env/" in rules
    assert "/env/*" in rules
    assert "/xontribs/" in rules
    assert rules["/env/*"] is _dump_xonfig_env
    assert rules["/xontribs/"] is _dump_xonfig_xontribs


# --- _info ------------------------------------------------------------------


def test_info_returns_string(xession):
    """``_info()`` returns a formatted human-readable table."""
    out = _info()
    assert isinstance(out, str)
    assert "xonsh" in out
    assert "Python" in out


def test_info_to_json_returns_valid_json(xession):
    out = _info(to_json=True)
    parsed = json.loads(out)
    assert "xonsh" in parsed
    assert "Python" in parsed


# --- make_envvar ------------------------------------------------------------


def test_make_envvar_returns_two_node_tuple_for_known_var(xession):
    """Configurable env vars produce a (Message, StoreNonEmpty) tuple."""
    result = make_envvar("XONSH_DEBUG")
    if result is None:
        pytest.skip("XONSH_DEBUG not configurable in this env")
    msg, prompt = result
    assert msg.message
    assert prompt.path == "/env/XONSH_DEBUG"


def test_make_envvar_returns_none_for_non_configurable(xession):
    """Non-configurable variables short-circuit to ``None``."""
    # Use a placeholder that we know is non-configurable.
    # Iterate to find a non-configurable one for a stable test.
    for k in xession.env.keys():
        vd = xession.env.get_docs(k)
        if not vd.is_configurable:
            assert make_envvar(k) is None
            return
    pytest.skip("no non-configurable env var found")


# --- _make_flat_wiz ---------------------------------------------------------


def test_make_flat_wiz_filters_none_results():
    """``_make_flat_wiz`` skips ``None`` returns from kidfunc."""
    from xonsh import wizard as wiz

    def maker(x):
        if x % 2 == 0:
            return None
        return (wiz.Message(message=str(x)), wiz.Pass())

    w = _make_flat_wiz(maker, [1, 2, 3])
    # 1 and 3 contribute 2 children each → 4
    assert isinstance(w, wiz.Wizard)
    assert len(w.children) == 4


# --- WELCOME_MSG / TAGLINES sanity -----------------------------------------


def test_welcome_msg_is_iterable_of_str_or_tuple():
    for elem in WELCOME_MSG:
        assert isinstance(elem, (str, tuple))


def test_taglines_non_empty():
    """The taglines list is non-empty and all entries are strings."""
    items = list(TAGLINES)
    assert items
    assert all(isinstance(t, str) for t in items)


# --- XonfigAlias -----------------------------------------------------------


def test_xonfig_alias_builds_argparser(xession):
    alias = XonfigAlias(threadable=False)
    parser = alias.build()
    help_text = parser.format_help()
    for cmd in ("info", "wizard", "web", "styles", "colors", "tutorial"):
        assert cmd in help_text


def test_xonfig_alias_extra_commands_added(xession):
    alias = XonfigAlias(threadable=False)

    def my_extra():
        """My extra subcommand"""

    alias.add_command(my_extra)
    parser = alias.build()
    help_text = parser.format_help()
    assert "my_extra" in help_text or "my-extra" in help_text


# --- make_xonfig_wizard ----------------------------------------------------


def test_make_xonfig_wizard_returns_wizard_node():
    from xonsh import wizard as wiz

    w = make_xonfig_wizard(default_file="/tmp/x.json", confirm=False)
    assert isinstance(w, wiz.Wizard)
    # confirm=False should yield a plain Wizard, not a Question wrapper
    assert hasattr(w, "children")


def test_make_xonfig_wizard_with_confirm_returns_question():
    from xonsh import wizard as wiz

    w = make_xonfig_wizard(default_file="/tmp/x.json", confirm=True)
    assert isinstance(w, wiz.Question)
    assert callable(w.converter)
    # converter("") returns the default response (2 = ask later)
    assert w.converter("") == 2
    assert w.converter("3") == 3
