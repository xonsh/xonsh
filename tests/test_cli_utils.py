"""Test module xonsh/cli_utils.py"""
from xonsh import cli_utils


def func_with_doc(param: str, multi: str) -> str:
    """func doc
    multi-line

    Parameters
    ----------
    param
        param doc
    multi
        param doc
        multi line

    Returns
    -------
    str
        return doc
    """
    return param + multi


def test_get_doc_param():
    assert cli_utils.get_doc(func_with_doc).splitlines() == [
        "func doc",
        "multi-line",
    ]
    assert cli_utils.get_doc(func_with_doc, "param").splitlines() == [
        "param doc",
    ]
    assert cli_utils.get_doc(func_with_doc, "multi").splitlines() == [
        "param doc",
        "multi line",
    ]
    assert cli_utils.get_doc(func_with_doc, epilog=True).splitlines() == [
        "Returns",
        "-------",
        "str",
        "    return doc",
    ]


def test_generated_parser():
    from xonsh.completers._aliases import CompleterAlias

    alias = CompleterAlias()

    assert alias.parser.description

    positionals = alias.parser._get_positional_actions()
    add_cmd = positionals[0].choices["add"]
    assert "Add a new completer" in add_cmd.description
    assert (
        alias.parser.format_usage()
        == "usage: completer [-h] {add,remove,rm,list,ls} ...\n"
    )
    assert add_cmd.format_usage() == "usage: completer add [-h] name func [pos]\n"
