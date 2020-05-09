"""Tests pygments hooks."""
import pytest
import os
import stat

from tempfile import TemporaryDirectory

from xonsh.pyghooks import (
    XonshStyle,
    Color,
    color_name_to_pygments_code,
    code_by_name,
    color_file,
    file_color_tokens,
)

from xonsh.environ import LsColors
from tools import skip_if_on_windows


@pytest.fixture
def xonsh_builtins_LS_COLORS(xonsh_builtins):
    """Xonsh environment including LS_COLORS"""
    e = xonsh_builtins.__xonsh__.env
    lsc = LsColors(LsColors.default_settings)
    xonsh_builtins.__xonsh__.env["LS_COLORS"] = lsc
    xonsh_builtins.__xonsh__.shell.shell_type = "prompt_toolkit"
    # styler = XonshStyle()  # default style
    # xonsh_builtins.__xonsh__.shell.shell.styler = styler
    # can't really instantiate XonshStyle separate from a shell??

    yield xonsh_builtins
    xonsh_builtins.__xonsh__.env = e


DEFAULT_STYLES = {
    # Reset
    Color.NO_COLOR: "noinherit",  # Text Reset
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
        ("NO_COLOR", "noinherit"),
        ("RED", "ansired"),
        ("BACKGROUND_RED", "bg:ansired"),
        ("BACKGROUND_INTENSE_RED", "bg:ansibrightred"),
        ("BOLD_RED", "bold ansired"),
        ("UNDERLINE_RED", "underline ansired"),
        ("BOLD_UNDERLINE_RED", "bold underline ansired"),
        ("UNDERLINE_BOLD_RED", "underline bold ansired"),
        # test unsupported modifiers
        ("BOLD_FAINT_RED", "bold ansired"),
        ("BOLD_SLOWBLINK_RED", "bold ansired"),
        ("BOLD_FASTBLINK_RED", "bold ansired"),
        ("BOLD_INVERT_RED", "bold ansired"),
        ("BOLD_CONCEAL_RED", "bold ansired"),
        ("BOLD_STRIKETHROUGH_RED", "bold ansired"),
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
        ("NO_COLOR", "noinherit"),
        ("RED", "ansired"),
        ("BACKGROUND_RED", "bg:ansired"),
        ("BACKGROUND_INTENSE_RED", "bg:ansibrightred"),
        ("BOLD_RED", "bold ansired"),
        ("UNDERLINE_RED", "underline ansired"),
        ("BOLD_UNDERLINE_RED", "bold underline ansired"),
        ("UNDERLINE_BOLD_RED", "underline bold ansired"),
        # test unsupported modifiers
        ("BOLD_FAINT_RED", "bold ansired"),
        ("BOLD_SLOWBLINK_RED", "bold ansired"),
        ("BOLD_FASTBLINK_RED", "bold ansired"),
        ("BOLD_INVERT_RED", "bold ansired"),
        ("BOLD_CONCEAL_RED", "bold ansired"),
        ("BOLD_STRIKETHROUGH_RED", "bold ansired"),
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
        (("NO_COLOR",), Color.NO_COLOR, "noinherit"),
        (("GREEN",), Color.GREEN, "ansigreen"),
        (("BOLD_RED",), Color.BOLD_RED, "bold ansired"),
        (
            ("BACKGROUND_BLACK", "BOLD_GREEN"),
            Color.BACKGROUND_BLACK__BOLD_GREEN,
            "bg:ansiblack bold ansigreen",
        ),
    ],
)
def test_color_token_by_name(
    in_tuple, exp_ct, exp_ansi_colors, xonsh_builtins_LS_COLORS
):
    from xonsh.pyghooks import XonshStyle, color_token_by_name

    xs = XonshStyle()
    styles = xs.styles
    ct = color_token_by_name(in_tuple, styles)
    ansi_colors = styles[ct]  # if keyerror, ct was not cached
    assert ct == exp_ct, "returned color token is right"
    assert ansi_colors == exp_ansi_colors, "color token mapped to correct color string"


def test_XonshStyle_init_file_color_tokens(xonsh_builtins_LS_COLORS):
    xs = XonshStyle()
    assert xs.styles
    assert type(file_color_tokens) is dict
    assert set(file_color_tokens.keys()) == set(
        xonsh_builtins_LS_COLORS.__xonsh__.env["LS_COLORS"].keys()
    )


_cf = {
    "rs": "regular",
    "di": "simple_dir",
    "ln": "simple_link",
    "mh": None,
    "pi": "pipe",
    "so": None,
    "do": None,
    # bug ci failures: 'bd': '/dev/sda',
    # bug ci failures:'cd': '/dev/tty',
    "or": "orphan_link",
    "mi": None,
    "su": "set_uid",
    "sg": "set_gid",
    "ca": None,
    "tw": "sticky_ow_dir",
    "ow": "other_writable_dir",
    "st": "sticky_dir",
    "ex": "executable",
    "*.emf": "foo.emf",
    "*.zip": "foo.zip",
    "*.ogg": "foo.ogg",
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
                if k in ("di", "rg"):
                    pass
                elif k == "ex":
                    os.chmod(file_path, stat.S_IXUSR)
                elif k == "ln":
                    os.rename(file_path, file_path + "_target")
                    os.symlink(file_path + "_target", file_path)
                elif k == "or":
                    os.rename(file_path, file_path + "_target")
                    os.symlink(file_path + "_target", file_path)
                    os.remove(file_path + "_target")
                elif k == "pi":
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
                else:
                    pass  # cauterize those elseless ifs!

        yield tempdir

    pass  # tempdir get cleaned up here.


@pytest.mark.parametrize(
    "key,file_path", [(key, file_path) for key, file_path in _cf.items() if file_path]
)
@skip_if_on_windows
def test_colorize_file(key, file_path, colorizable_files, xonsh_builtins_LS_COLORS):
    xonsh_builtins_LS_COLORS.__xonsh__.shell.shell.styler = (
        XonshStyle()
    )  # default style
    ffp = colorizable_files + "/" + file_path
    mode = (os.lstat(ffp)).st_mode
    color_token, color_key = color_file(ffp, mode)
    assert color_key == key, "File classified as expected kind"
    assert color_token == file_color_tokens[key], "Color token is as expected"
