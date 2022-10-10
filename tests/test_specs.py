import pytest

from xonsh.procs.specs import SubprocSpec
from xonsh.tools import XonshError


def test_on_command_not_found_fires(xession):
    xession.env.update(
        dict(
            XONSH_INTERACTIVE=True,
        )
    )

    fired = False

    def my_handler(cmd, **kwargs):
        nonlocal fired
        assert cmd[0] == "xonshcommandnotfound"
        fired = True

    xession.builtins.events.on_command_not_found(my_handler)
    subproc = SubprocSpec.build(["xonshcommandnotfound"])
    with pytest.raises(XonshError) as expected:
        subproc.run()
    assert "command not found: xonshcommandnotfound" in str(expected.value)
    assert fired


def test_on_command_not_found_doesnt_fire_in_non_interactive_mode(xession):
    xession.env.update(
        dict(
            XONSH_INTERACTIVE=False,
        )
    )

    fired = False

    def my_handler(cmd, **kwargs):
        nonlocal fired
        assert cmd[0] == "xonshcommandnotfound"
        fired = True

    xession.builtins.events.on_command_not_found(my_handler)
    subproc = SubprocSpec.build(["xonshcommandnotfound"])
    with pytest.raises(XonshError) as expected:
        subproc.run()
    assert "command not found: xonshcommandnotfound" in str(expected.value)
    assert not fired
