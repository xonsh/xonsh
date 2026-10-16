"""Regression tests for the metadata produced by ``xonsh.cli_utils.Arg``."""

import argparse
from typing import Annotated

import pytest

from xonsh import cli_utils
from xonsh.cli_utils import Arg
from xonsh.tools import to_bool


def _completer(**_):
    yield "x"


class _Action(argparse.Action):
    pass


@pytest.mark.parametrize(
    "spec, exp",
    [
        (Arg(), "Arg()"),
        (Arg(nargs="+"), "Arg(nargs='+')"),
        (Arg("-n", "--name", nargs=2), "Arg('-n', '--name', nargs=2)"),
        (Arg(type=to_bool), "Arg(type=to_bool)"),
        (Arg(type=int), "Arg(type=int)"),
        (Arg(completer=_completer), "Arg(completer=_completer)"),
        (Arg(action=_Action), "Arg(action=_Action)"),
        (Arg(type=lambda x: x), "Arg(type=<lambda>)"),
    ],
)
def test_arg_repr_is_stable(spec, exp):
    # the default repr of a function holds a memory address
    assert repr(spec) == exp
    assert " at 0x" not in repr(Annotated[str, spec])


def test_arg_still_a_hashable_args_kwargs_pair():
    spec = Arg("-n", completer=_completer, nargs="?")
    assert isinstance(spec, tuple)
    args, kwargs = spec
    assert args == ("-n",)
    assert dict(kwargs) == {"nargs": "?", "completer": _completer}
    assert spec == (("-n",), (("nargs", "?"), ("completer", _completer)))
    hash(Annotated[str, spec])


def test_arg_metadata_builds_parser():
    def func(
        name: Annotated[str, Arg(completer=_completer)],
        flag: Annotated[bool, Arg("-f", "--flag")] = False,
        toggle: Annotated[bool, Arg(type=to_bool)] = False,
    ):
        """Func doc"""

    parser = cli_utils.make_parser(func)
    cli_utils.add_args(parser, func)
    ns = parser.parse_args(["me", "-f", "yes"])
    assert (ns.name, ns.flag, ns.toggle) == ("me", True, True)
    actions = {act.dest: act for act in parser._actions}
    assert actions["name"].completer is _completer
