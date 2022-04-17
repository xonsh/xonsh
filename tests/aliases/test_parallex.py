import pytest

from xonsh.pytest.tools import skip_if_on_windows


@pytest.fixture
def parallex(xsh_with_aliases):
    return xsh_with_aliases.aliases["parallex"]


def test_exec(parallex, capfd):
    parallex(["mypy --version", "flake8 --version"])

    out, _ = capfd.readouterr()
    assert "mypy" in out
    assert "flake" in out


@skip_if_on_windows
def test_shell_ordered(parallex, capfd):
    parallex(
        ["echo 1; sleep 0.02; echo 2", "echo 3; sleep 0.05; echo 4", "--shell"],
    )

    out, _ = capfd.readouterr()
    assert "".join(out.split()) == "1234"


@skip_if_on_windows
def test_shell_interleaved(parallex, capfd):
    parallex(
        [
            "echo 1; sleep 0.04; echo 2",
            "echo 3; sleep 0.06; echo 4",
            "--shell",
            "--no-order",
        ],
    )

    out, _ = capfd.readouterr()
    assert "".join(out.split()) == "1324"
