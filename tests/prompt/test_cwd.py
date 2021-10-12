from xonsh.prompt.cwd import _replace_home_cwd
from xonsh.built_ins import XSH


def test_cwd_escapes_curly_brackets_with_more_curly_brackets():
    XSH.env["PWD"] = "{foo}"
    assert _replace_home_cwd() == "{{foo}}"

    XSH.env["PWD"] = "{{foo}}"
    assert _replace_home_cwd() == "{{{{foo}}}}"

    XSH.env["PWD"] = "{"
    assert _replace_home_cwd() == "{{"

    XSH.env["PWD"] = "}}"
    assert _replace_home_cwd() == "}}}}"
