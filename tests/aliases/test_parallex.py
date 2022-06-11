import pytest

from xonsh.pytest import tools


@pytest.fixture
def parallex(xsh_with_aliases):
    return xsh_with_aliases.aliases["parallex"]


def test_exec(parallex, capfd):
    parallex(["python --version", "pip --version"])

    out, _ = capfd.readouterr()
    assert "Python" in out
    assert "pip" in out


@tools.skip_if_on_windows
@pytest.mark.parametrize(
    "expected, args",
    [
        pytest.param("1234", [], id="ordered"),
        pytest.param("1324", ["--no-order"], id="interleaved"),
    ],
)
def test_shell_ordered(expected, args, parallex, capfd):
    parallex(
        [
            "python -uc 'import time; print(1); time.sleep(0.01); print(2)'",
            # elapse some time, so that the order will not be messed up in environments like macos
            "python -uc 'import time; time.sleep(0.0001); print(3); time.sleep(0.03); print(4)'",
            "--shell",
            *args,
        ],
    )

    out, _ = capfd.readouterr()
    assert "".join(out.split()) == expected
