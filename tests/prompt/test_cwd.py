from xonsh.prompt.cwd import _replace_home_cwd


def test_cwd_escapes_curly_brackets_with_more_curly_brackets(xession, tmpdir):
    xession.env["HOME"] = str(tmpdir)
    xession.env["PWD"] = "{foo}"
    assert _replace_home_cwd() == "{{foo}}"

    xession.env["PWD"] = "{{foo}}"
    assert _replace_home_cwd() == "{{{{foo}}}}"

    xession.env["PWD"] = "{"
    assert _replace_home_cwd() == "{{"

    xession.env["PWD"] = "}}"
    assert _replace_home_cwd() == "}}}}"
