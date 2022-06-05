import pytest


@pytest.fixture
def fish_completer(tmpdir, xession, load_xontrib, fake_process):
    """vox Alias function"""
    load_xontrib("fish_completer")
    xession.env.update(
        dict(
            XONSH_DATA_DIR=str(tmpdir),
            XONSH_SHOW_TRACEBACK=True,
        )
    )

    fake_process.register_subprocess(
        command=["fish", fake_process.any()],
        # completion for "git chec"
        stdout=b"""\
cherry-pick	Apply the change introduced by an existing commit
checkout	Checkout and switch to a branch""",
    )

    return fake_process


def test_fish_completer(fish_completer, check_completer):
    assert check_completer("git", prefix="chec") == {"checkout"}
