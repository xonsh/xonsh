import pytest


@pytest.mark.parametrize(
    "args, prefix, exp",
    [
        (
            "xonfig",
            "-",
            {"-h", "--help"},
        ),
        (
            "xonfig colors",
            "b",
            {"blue", "brown"},
        ),
    ],
)
def test_xonfig(args, prefix, exp, xsh_with_aliases, monkeypatch, check_completer):
    from xonsh import xonfig

    monkeypatch.setattr(xonfig, "color_style_names", lambda: ["blue", "brown", "other"])
    assert check_completer(args, prefix=prefix) == exp


def test_xontrib(xsh_with_aliases, check_completer):
    assert check_completer("xontrib", prefix="l") == {"list", "load"}
