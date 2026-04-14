"""Tests pygments hooks."""

import os
import pathlib
import stat
from tempfile import TemporaryDirectory

import pytest

from xonsh.environ import LsColors
from xonsh.platform import ON_WINDOWS
from xonsh.pyghooks import (
    XSH,
    Color,
    Token,
    XonshConsoleLexer,
    XonshLexer,
    XonshStyle,
    code_by_name,
    color_file,
    color_name_to_pygments_code,
    file_color_tokens,
    get_style_by_name,
    register_custom_pygments_style,
)


@pytest.fixture
def xs_LS_COLORS(xession, os_env, monkeypatch):
    """Xonsh environment including LS_COLORS"""

    # original env is needed on windows. since it will skip enhanced coloring
    # for some emulators
    monkeypatch.setattr(xession, "env", os_env)

    lsc = LsColors(LsColors.default_settings)
    xession.env["LS_COLORS"] = lsc

    # todo: a separate test for this as True
    xession.env["INTENSIFY_COLORS_ON_WIN"] = False

    xession.shell.shell_type = "prompt_toolkit"
    xession.shell.shell.styler = XonshStyle()  # default style

    yield xession


DEFAULT_STYLES = {
    # Reset
    Color.RESET: "noinherit",  # Text Reset
    # Regular Colors
    Color.BLACK: "ansiblack",
    Color.BLUE: "ansiblue",
    Color.CYAN: "ansicyan",
    Color.GREEN: "ansigreen",
    Color.PURPLE: "ansimagenta",
    Color.RED: "ansired",
    Color.WHITE: "ansigray",
    Color.YELLOW: "ansiyellow",
    Color.INTENSE_BLACK: "ansibrightblack",
    Color.INTENSE_BLUE: "ansibrightblue",
    Color.INTENSE_CYAN: "ansibrightcyan",
    Color.INTENSE_GREEN: "ansibrightgreen",
    Color.INTENSE_PURPLE: "ansibrightmagenta",
    Color.INTENSE_RED: "ansibrightred",
    Color.INTENSE_WHITE: "ansiwhite",
    Color.INTENSE_YELLOW: "ansibrightyellow",
}


@pytest.mark.parametrize(
    "name, exp",
    [
        ("RESET", "noinherit"),
        ("RED", "ansired"),
        ("BACKGROUND_RED", "bg:ansired"),
        ("BACKGROUND_INTENSE_RED", "bg:ansibrightred"),
        ("BOLD_RED", "bold ansired"),
        ("UNDERLINE_RED", "underline ansired"),
        ("BOLD_UNDERLINE_RED", "bold underline ansired"),
        ("UNDERLINE_BOLD_RED", "underline bold ansired"),
        # test supported modifiers
        ("BOLD_SLOWBLINK_RED", "bold blink ansired"),
        ("BOLD_FASTBLINK_RED", "bold blink ansired"),
        ("BOLD_INVERT_RED", "bold reverse ansired"),
        ("BOLD_CONCEAL_RED", "bold hidden ansired"),
        ("BOLD_STRIKETHROUGH_RED", "bold strike ansired"),
        ("INVERT_WHITE", "reverse ansigray"),
        ("SLOWBLINK_RED", "blink ansired"),
        ("CONCEAL_GREEN", "hidden ansigreen"),
        ("STRIKETHROUGH_BLUE", "strike ansiblue"),
        # test unsupported modifiers
        ("BOLD_FAINT_RED", "bold ansired"),
        # test off modifiers
        ("BOLDOFF_RED", "nobold ansired"),
        ("ITALICOFF_RED", "noitalic ansired"),
        ("UNDERLINEOFF_RED", "nounderline ansired"),
        ("BLINKOFF_RED", "noblink ansired"),
        ("INVERTOFF_RED", "noreverse ansired"),
        ("STRIKETHROUGHOFF_RED", "nostrike ansired"),
        # test hexes
        ("#000", "#000"),
        ("#000000", "#000000"),
        ("BACKGROUND_#000", "bg:#000"),
        ("BACKGROUND_#000000", "bg:#000000"),
        ("BG#000", "bg:#000"),
        ("bg#000000", "bg:#000000"),
    ],
)
def test_color_name_to_pygments_code(name, exp):
    styles = DEFAULT_STYLES.copy()
    obs = color_name_to_pygments_code(name, styles)
    assert obs == exp


@pytest.mark.parametrize(
    "name, exp",
    [
        ("RESET", "noinherit"),
        ("RED", "ansired"),
        ("BACKGROUND_RED", "bg:ansired"),
        ("BACKGROUND_INTENSE_RED", "bg:ansibrightred"),
        ("BOLD_RED", "bold ansired"),
        ("UNDERLINE_RED", "underline ansired"),
        ("BOLD_UNDERLINE_RED", "bold underline ansired"),
        ("UNDERLINE_BOLD_RED", "underline bold ansired"),
        # test supported modifiers
        ("BOLD_SLOWBLINK_RED", "bold blink ansired"),
        ("BOLD_FASTBLINK_RED", "bold blink ansired"),
        ("BOLD_INVERT_RED", "bold reverse ansired"),
        ("BOLD_CONCEAL_RED", "bold hidden ansired"),
        ("BOLD_STRIKETHROUGH_RED", "bold strike ansired"),
        # test unsupported modifiers
        ("BOLD_FAINT_RED", "bold ansired"),
        # test hexes
        ("#000", "#000"),
        ("#000000", "#000000"),
        ("BACKGROUND_#000", "bg:#000"),
        ("BACKGROUND_#000000", "bg:#000000"),
        ("BG#000", "bg:#000"),
        ("bg#000000", "bg:#000000"),
    ],
)
def test_code_by_name(name, exp):
    styles = DEFAULT_STYLES.copy()
    obs = code_by_name(name, styles)
    assert obs == exp


@pytest.mark.parametrize(
    "in_tuple, exp_ct, exp_ansi_colors",
    [
        (("RESET",), Color.RESET, "noinherit"),
        (("GREEN",), Color.GREEN, "ansigreen"),
        (("BOLD_RED",), Color.BOLD_RED, "bold ansired"),
        (
            ("BACKGROUND_BLACK", "BOLD_GREEN"),
            Color.BACKGROUND_BLACK__BOLD_GREEN,
            "bg:ansiblack bold ansigreen",
        ),
    ],
)
def test_color_token_by_name(in_tuple, exp_ct, exp_ansi_colors, xs_LS_COLORS):
    from xonsh.pyghooks import XonshStyle, color_token_by_name

    xs = XonshStyle()
    styles = xs.styles
    ct = color_token_by_name(in_tuple, styles)
    ansi_colors = styles[ct]  # if keyerror, ct was not cached
    assert ct == exp_ct, "returned color token is right"
    assert ansi_colors == exp_ansi_colors, "color token mapped to correct color string"


def test_XonshStyle_init_file_color_tokens(xs_LS_COLORS, monkeypatch):
    keys = list(file_color_tokens)
    for n in keys:
        monkeypatch.delitem(file_color_tokens, n)
    xs = XonshStyle()
    assert xs.styles
    assert isinstance(file_color_tokens, dict)
    assert set(file_color_tokens.keys()) == set(xs_LS_COLORS.env["LS_COLORS"].keys())


# parameterized tests for file colorization
# note 'ca' is checked by standalone test.
# requires privilege to create a file with capabilities

if ON_WINDOWS:
    # file coloring support is very limited on Windows, only test the cases we can easily make work
    # If you care about file colors, use Windows Subsystem for Linux, or another OS.

    _cf = {
        "fi": "regular",
        "di": "simple_dir",
        "ln": None,  # symlinks require elevated privileges on Windows
        "pi": None,
        "so": None,
        "do": None,
        # bug ci failures: 'bd': '/dev/sda',
        # bug ci failures:'cd': '/dev/tty',
        "or": None,  # symlinks require elevated privileges on Windows
        "mi": None,  # never used
        "su": None,
        "sg": None,
        "ca": None,  # Separate special case test,
        "tw": None,
        "ow": None,
        "st": None,
        "ex": None,  # executable is a filetype test on Windows.
        "*.emf": "foo.emf",
        "*.zip": "foo.zip",
        "*.ogg": "foo.ogg",
        "mh": "hard_link",
    }
else:
    # full-fledged, VT100 based infrastructure
    _cf = {
        "fi": "regular",
        "di": "simple_dir",
        "ln": "sym_link",
        "pi": "pipe",
        "so": None,
        "do": None,
        # bug ci failures: 'bd': '/dev/sda',
        # bug ci failures:'cd': '/dev/tty',
        "or": "orphan",
        "mi": None,  # never used
        "su": "set_uid",
        "sg": "set_gid",
        "ca": None,  # Separate special case test,
        "tw": "sticky_ow_dir",
        "ow": "other_writable_dir",
        "st": "sticky_dir",
        "ex": "executable",
        "*.emf": "foo.emf",
        "*.zip": "foo.zip",
        "*.ogg": "foo.ogg",
        "mh": "hard_link",
    }


@pytest.fixture(scope="module")
def colorizable_files():
    """populate temp dir with sample files.
    (too hard to emit indivual test cases when fixture invoked in mark.parametrize)"""

    with TemporaryDirectory() as tempdir:
        for k, v in _cf.items():
            if v is None:
                continue
            if v.startswith("/"):
                file_path = v
            else:
                file_path = tempdir + "/" + v
            try:
                os.lstat(file_path)
            except FileNotFoundError:
                if file_path.endswith("_dir"):
                    os.mkdir(file_path)
                else:
                    open(file_path, "a").close()
                if k in ("di", "fi"):
                    pass
                elif k == "ex":
                    os.chmod(file_path, stat.S_IRWXU)  # tmpdir on windows need u+w
                elif k == "ln":  # cook ln test case.
                    os.chmod(file_path, stat.S_IRWXU)  # link to *executable* file
                    os.rename(file_path, file_path + "_target")
                    os.symlink(file_path + "_target", file_path)
                elif k == "or":
                    os.rename(file_path, file_path + "_target")
                    os.symlink(file_path + "_target", file_path)
                    os.remove(file_path + "_target")
                elif k == "pi":  # not on Windows
                    os.remove(file_path)
                    os.mkfifo(file_path)
                elif k == "su":
                    os.chmod(file_path, stat.S_ISUID)
                elif k == "sg":
                    os.chmod(file_path, stat.S_ISGID)
                elif k == "st":
                    os.chmod(
                        file_path, stat.S_ISVTX | stat.S_IRUSR | stat.S_IWUSR
                    )  # TempDir requires o:r
                elif k == "tw":
                    os.chmod(
                        file_path,
                        stat.S_ISVTX | stat.S_IWOTH | stat.S_IRUSR | stat.S_IWUSR,
                    )
                elif k == "ow":
                    os.chmod(file_path, stat.S_IWOTH | stat.S_IRUSR | stat.S_IWUSR)
                elif k == "mh":
                    os.rename(file_path, file_path + "_target")
                    os.link(file_path + "_target", file_path)
                else:
                    pass  # cauterize those elseless ifs!

                try:
                    os.symlink(file_path, file_path + "_symlink")
                except OSError:
                    pass  # symlinks may require elevated privileges on Windows

        yield tempdir

    pass  # tempdir get cleaned up here.


@pytest.mark.parametrize(
    "key,file_path",
    [(key, file_path) for key, file_path in _cf.items() if file_path],
)
def test_colorize_file(key, file_path, colorizable_files, xs_LS_COLORS):
    """test proper file codes with symlinks colored normally"""
    ffp = colorizable_files + "/" + file_path
    stat_result = os.lstat(ffp)
    color_token, color_key = color_file(ffp, stat_result)
    assert color_key == key, "File classified as expected kind"
    assert color_token == file_color_tokens[key], "Color token is as expected"


@pytest.mark.skipif(
    ON_WINDOWS, reason="symlinks require elevated privileges on Windows"
)
@pytest.mark.parametrize(
    "key,file_path",
    [(key, file_path) for key, file_path in _cf.items() if file_path],
)
def test_colorize_file_symlink(key, file_path, colorizable_files, xs_LS_COLORS):
    """test proper file codes with symlinks colored target."""
    xs_LS_COLORS.env["LS_COLORS"]["ln"] = "target"
    ffp = colorizable_files + "/" + file_path + "_symlink"
    stat_result = os.lstat(ffp)
    assert stat.S_ISLNK(stat_result.st_mode)

    _, color_key = color_file(ffp, stat_result)

    try:
        tar_stat_result = os.stat(ffp)  # stat the target of the link
        tar_ffp = str(pathlib.Path(ffp).resolve())
        _, tar_color_key = color_file(tar_ffp, tar_stat_result)
        if tar_color_key.startswith("*"):
            tar_color_key = (
                "fi"  # all the *.* zoo, link is colored 'fi', not target type.
            )
    except FileNotFoundError:  # orphan symlinks always colored 'or'
        tar_color_key = "or"  # Fake if for missing file

    assert color_key == tar_color_key, "File classified as expected kind, via symlink"


import xonsh.lib.lazyimps


def test_colorize_file_ca(xs_LS_COLORS, monkeypatch):
    def mock_os_listxattr(*args, **kwards):
        return ["security.capability"]

    monkeypatch.setattr(xonsh.pyghooks, "os_listxattr", mock_os_listxattr)

    with TemporaryDirectory() as tmpdir:
        file_path = tmpdir + "/cap_file"
        open(file_path, "a").close()
        os.chmod(
            file_path, stat.S_IRWXU
        )  # ca overrides ex, leave file deletable on Windows
        color_token, color_key = color_file(file_path, os.lstat(file_path))

        assert color_key == "ca"


@pytest.mark.parametrize(
    "name, styles, refrules",
    [
        ("test1", {}, {}),  # empty styles
        (
            "test2",
            {Token.Literal.String.Single: "#ff0000"},
            {Token.Literal.String.Single: "#ff0000"},
        ),  # Token
        (
            "test3",
            {"Token.Literal.String.Single": "#ff0000"},
            {Token.Literal.String.Single: "#ff0000"},
        ),  # str key
        (
            "test4",
            {"Literal.String.Single": "#ff0000"},
            {Token.Literal.String.Single: "#ff0000"},
        ),  # short str key
        (
            "test5",
            {"completion-menu.completion.current": "#00ff00"},
            {Token.PTK.CompletionMenu.Completion.Current: "#00ff00"},
        ),  # ptk style
        (
            "test6",
            {"RED": "#ff0000"},
            {Token.Color.RED: "#ff0000"},
        ),  # short color name
    ],
)
def test_register_custom_pygments_style(name, styles, refrules):
    register_custom_pygments_style(name, styles)
    style = get_style_by_name(name)

    # registration succeeded
    assert style is not None

    # check rules
    for rule, color in refrules.items():
        assert rule in style.styles
        assert style.styles[rule] == color


def test_register_custom_style_inherits_xonsh_base():
    """Custom style based on 'default' should inherit XONSH_BASE_STYLE ANSI names,
    not pygments' hex codes.

    Regression test for https://github.com/xonsh/xonsh/issues/5162
    """
    from pygments.token import Name

    from xonsh.pyghooks import XONSH_BASE_STYLE

    register_custom_pygments_style("test_inherit", {}, base="default")
    style = get_style_by_name("test_inherit")

    assert style.styles[Name.Variable] == XONSH_BASE_STYLE[Name.Variable]


def test_pygments_style_no_bg_in_palette():
    """Color.* tokens must never map to the theme's background color.

    Regression test for https://github.com/xonsh/xonsh/issues/5001
    """
    from xonsh.pyghooks import STYLES, pygments_style_by_name

    # Clear cached style so it's regenerated with the fix
    STYLES.pop("gruvbox-dark", None)
    cmap = pygments_style_by_name("gruvbox-dark")

    bg_color = get_style_by_name("gruvbox-dark").background_color
    for token, color in cmap.items():
        assert color != bg_color, f"{token} mapped to background color {bg_color}"


@pytest.mark.parametrize(
    "code, expect_error",
    [
        ("import json", False),
        ("import qweqweqwe", True),
        ("import os.path", False),
        ("import os, qweqweqwe", True),
        ("from os import path", False),
        ("from qweqweqwe import foo", True),
        ("from . import something", False),
    ],
)
def test_import_module_validation(code, expect_error):
    """Non-existent modules in import statements should be highlighted as Error."""
    from xonsh.pyghooks import XonshLexer

    lexer = XonshLexer()
    tokens = list(lexer.get_tokens(code))
    has_error = any(t == Token.Error for t, _ in tokens)
    assert has_error == expect_error, f"{code!r}: tokens={tokens}"


@pytest.mark.parametrize(
    "name, expect_error",
    [
        ("len", False),  # builtin
        ("True", False),  # keyword
        ("myvar", False),  # in ctx
        ("undefined", True),  # not defined anywhere
    ],
)
def test_at_bracket_name_validation(name, expect_error, xession):
    """Undefined names inside @() should be highlighted as Error."""
    from xonsh.pyghooks import XonshLexer

    xession.ctx["myvar"] = 42
    lexer = XonshLexer()
    tokens = list(lexer.get_tokens(f"echo @({name})"))
    has_error = any(t == Token.Error for t, _ in tokens)
    assert has_error == expect_error, f"@({name}): tokens={tokens}"


def test_can_use_xonsh_lexer_without_xession(xession, monkeypatch):
    # When Xonsh is used as a library and simply for its lexer plugin, the
    # xession's env can be unset, so test that it can yield tokens without
    # that env being set.
    monkeypatch.setattr(xession, "env", None)

    assert XSH.env is None
    lexer = XonshLexer()
    assert XSH.env is not None
    list(lexer.get_tokens_unprocessed("  some text"))


def _prompt_tokens(xsh_console_text):
    """Return the list of ``(token_type, value)`` tuples that
    ``XonshConsoleLexer`` produces for a given multi-line console text."""
    return list(XonshConsoleLexer().get_tokens(xsh_console_text))


def test_xonshcon_first_prompt_includes_trailing_space(xession):
    """The first-line ``@ `` prompt must be tokenised as a single
    ``Generic.Prompt`` token that includes the trailing space, so that
    stripping prompts from copy-paste leaves the command with no orphan
    leading space."""
    tokens = _prompt_tokens("@ echo hello\n")
    prompt = next((v for t, v in tokens if t is Token.Generic.Prompt), None)
    assert prompt == "@ "


def test_xonshcon_continuation_prompt_symmetric_with_first(xession):
    """Regression: a second ``@ ``-prefixed line used to be tokenised as
    ``(\\n@, Generic.Prompt)`` + ``( , Text)``, i.e. the leading newline
    was eaten by the prompt token while the trailing space was *not*.
    That made copy-paste produce ``"echo hello\\n cd $HOME"`` — with an
    orphan leading space on every continuation line. The fix splits the
    newline off into a plain ``Text`` token and includes the trailing
    space in the prompt, so both lines yield an identical ``"@ "``
    prompt token."""
    tokens = _prompt_tokens("@ echo hello\n@ cd $HOME\n")
    prompts = [v for t, v in tokens if t is Token.Generic.Prompt]
    # Exactly two prompts, both identical "@ " (with trailing space).
    assert prompts == ["@ ", "@ "]
    # The newline between the two command lines is a plain Text token,
    # NOT part of any Prompt span — so it survives clipboard stripping.
    assert any(t is Token.Text and v == "\n" for t, v in tokens)


def test_xonshcon_python_continuation_prompt_symmetric(xession):
    """Same regression for Python interactive prompts (``>>>`` / ``...``)."""
    tokens = _prompt_tokens(">>> x = 1\n>>> print(x)\n")
    prompts = [v for t, v in tokens if t is Token.Generic.Prompt]
    assert prompts == [">>> ", ">>> "]
    assert any(t is Token.Text and v == "\n" for t, v in tokens)


def test_xonshcon_copy_paste_strips_prompts_cleanly(xession):
    """End-to-end: stripping every ``Generic.Prompt`` token from the
    tokenised stream must yield the raw command text with correct line
    breaks and no orphan leading spaces."""
    text = "@ echo hello\n@ cd $HOME\n"
    tokens = _prompt_tokens(text)
    copied = "".join(v for t, v in tokens if t is not Token.Generic.Prompt)
    # Prompt stripped, newlines and command content preserved exactly.
    assert copied == "echo hello\ncd $HOME\n"


def _copy_simulated(text):
    """Simulate what the browser copies: strip every ``Generic.Prompt``
    and ``Generic.Output`` token from the lexer stream (that's what the
    CSS ``user-select: none`` on ``.gp`` + ``.go`` does).
    """
    return "".join(
        v
        for t, v in _prompt_tokens(text)
        if "Prompt" not in str(t) and "Output" not in str(t)
    )


def test_xonshcon_output_hash_comment_is_output(xession):
    """A line starting with ``#`` at column 0 is tokenised as
    ``Generic.Output`` (rendered in grey and excluded from copy).

    The preceding newline is included in the Output token so that
    stripping the output from the clipboard also strips the leading
    line break — otherwise a stray ``\\n`` leaks through and leaves a
    blank line between the previous and next code line.
    """
    tokens = _prompt_tokens("@ echo 1\n# 1 output line\n")
    outputs = [v for t, v in tokens if "Output" in str(t)]
    assert "\n# 1 output line" in outputs
    # And the simulated clipboard contains only the command:
    assert _copy_simulated("@ echo 1\n# 1 output line\n") == "echo 1\n"


def test_xonshcon_indented_hash_not_output(xession):
    """A ``#`` comment *inside* a continuation body (preceded by the
    2-space prompt-width compensation) must be treated as a regular
    Python comment, NOT as a documented output line."""
    text = "@ def f():\n      # python comment\n      return 1\n"
    tokens = _prompt_tokens(text)
    # The "# python comment" should NOT be tokenised as Generic.Output —
    # its leading 2 spaces get stripped and the rest flows into xonsh
    # highlighting as a Comment.
    outputs = [v for t, v in tokens if "Output" in str(t)]
    assert not any("python comment" in v for v in outputs)
    # And it survives copy-paste with 4 real Python spaces of indent:
    copied = _copy_simulated(text)
    assert "    # python comment" in copied
    assert "    return 1" in copied


def test_xonshcon_two_space_continuation_becomes_prompt(xession):
    """Continuation body lines start with 2 spaces of prompt-width
    compensation. Those 2 spaces must be tokenised as ``Generic.Prompt``
    so they're stripped from copy-paste, leaving the body with its real
    Python indentation."""
    text = "@ def qwe():\n      print(321)\n  qwe()\n"
    tokens = _prompt_tokens(text)
    # Find every Generic.Prompt token and confirm at least one of them
    # is the 2-space compensation, not a real ``@ `` prompt.
    prompts = [v for t, v in tokens if t is Token.Generic.Prompt]
    assert "  " in prompts, f"expected 2-space compensation prompt in {prompts}"

    copied = _copy_simulated(text)
    # ``print(321)`` keeps its real 4-space Python indent (6 − 2 = 4).
    assert "    print(321)" in copied
    # ``qwe()`` is at top level (2 − 2 = 0).
    assert "\nqwe()\n" in copied or copied.startswith("qwe()") or "\nqwe()" in copied
    # Nothing is indented at 6 spaces (i.e. the prompt-width spaces are gone).
    assert "      print" not in copied
    assert "  qwe()" not in copied


def test_xonshcon_blank_line_preserved_in_copy(xession):
    """Blank lines between command blocks must survive clipboard-strip
    (the separator is important for readable Python)."""
    text = "@ def f():\n      return 1\n\n@ def g():\n      return 2\n"
    copied = _copy_simulated(text)
    # Two function definitions separated by a blank line.
    assert copied == "def f():\n    return 1\n\ndef g():\n    return 2\n"


def test_xonshcon_full_users_example(xession):
    """End-to-end check of the canonical xonshcon convention the user
    wants: ``# ``-prefixed output lines, continuation lines with 2-space
    prompt-width compensation. Clipboard yields runnable Python."""
    text = (
        "@ echo 1\n"
        "# 1 output from command\n"
        "@ def qwe():\n"
        "      print(321)\n"
        "  qwe()\n"
        "# 321 output\n"
    )
    copied = _copy_simulated(text)
    # Prompts and ``# output`` lines are gone; real code remains with
    # correct Python indentation.
    assert copied == "echo 1\ndef qwe():\n    print(321)\nqwe()\n"
