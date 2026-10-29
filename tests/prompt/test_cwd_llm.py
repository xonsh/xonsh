import os

import pytest

from xonsh.prompt.base import PromptFields


@pytest.fixture
def fields(xession):
    return PromptFields(xession)


@pytest.mark.parametrize(
    "name, shown",
    [
        ("\n\n\n\nend\n", "\\n\\n\\n\\nend\\n"),
        ("a\tb", "a\\tb"),
        ("a\rb", "a\\rb"),
        ("\x1b[31mred", "\\x1b[31mred"),
        ("a\x7fb", "a\\x7fb"),
        ("a\x9bb", "a\\x9bb"),
        ("café 日本", "café 日本"),
    ],
)
@pytest.mark.parametrize("field", ["cwd", "short_cwd", "cwd_base"])
def test_cwd_fields_escape_control_characters(
    xession, fields, tmpdir, name, shown, field
):
    xession.env["HOME"] = str(tmpdir)
    xession.env["PWD"] = os.path.join(str(tmpdir), "dir", name)

    result = fields.pick(field)

    assert result.endswith(shown)
    assert result.isprintable()


def test_cwd_dir_escapes_control_characters(xession, fields, tmpdir):
    xession.env["HOME"] = str(tmpdir)
    xession.env["PWD"] = os.path.join(str(tmpdir), "a\nb", "end")

    result = fields.pick("cwd_dir")

    assert result.endswith("a\\nb" + os.sep)
    assert result.isprintable()


def test_dynamically_collapsed_cwd_escapes_control_characters(xession, fields, tmpdir):
    xession.env["HOME"] = str(tmpdir)
    xession.env["DYNAMIC_CWD_WIDTH"] = (20, "c")
    xession.env["PWD"] = os.path.join(str(tmpdir), "x\ny" * 10, "end\n")

    result = fields.pick("cwd")

    assert result.endswith("end\\n")
    assert result.isprintable()
