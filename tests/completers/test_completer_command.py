import pytest

from xonsh.completers._aliases import complete_aliases


@pytest.fixture
def mock_completer(monkeypatch, xsh_with_aliases):
    def dummy_completer(*_):
        return

    xsh = xsh_with_aliases
    monkeypatch.setattr(
        xsh, "_completers", {"one": dummy_completer, "two": complete_aliases}
    )
    monkeypatch.setattr(xsh, "ctx", {"three": lambda: 1, "four": lambda: 2})
    return xsh


@pytest.mark.parametrize(
    "args, positionals, options",
    [
        (
            "completer",
            {"add", "remove", "rm", "list", "ls", "complete"},
            {"--help", "-h"},
        ),
        (
            "completer add",
            set(),
            {"--help", "-h"},
        ),
        (
            "completer add newcompleter",
            {"three", "four"},
            {"--help", "-h"},
        ),
        (
            "completer add newcompleter three",
            {"<one", ">two", ">one", "<two", "end", "start"},
            {"--help", "-h"},
        ),
        (
            "completer remove",
            {"one", "two"},
            {"--help", "-h"},
        ),
        (
            "completer list",
            set(),
            {"--help", "-h"},
        ),
    ],
)
def test_completer_command(args, positionals, options, mock_completer, check_completer):
    assert check_completer(args) == positionals

    mock_completer.env["ALIAS_COMPLETIONS_OPTIONS_BY_DEFAULT"] = True
    assert check_completer(args) == positionals.union(options)
