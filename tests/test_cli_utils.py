"""Test module xonsh/cli_utils.py"""

from xonsh import cli_utils


def func_with_doc(param: str, multi: str, optional=False):
    """func doc
    multi-line

    Parameters
    ----------
    param
        param doc
    multi
        param doc
        multi line
    optional : -o, --opt
        an optional parameter with flags defined in description

    Returns
    -------
    str
        return doc
    """
    return param + multi, optional


def test_get_doc_param():
    doc = cli_utils.NumpyDoc(func_with_doc)
    assert doc.description.splitlines() == [
        "func doc",
        "multi-line",
    ]
    assert doc.epilog.splitlines() == [
        "Returns",
        "-------",
        "str",
        "    return doc",
    ]
    assert doc.params["param"].splitlines() == [
        "param doc",
    ]
    assert doc.params["multi"].splitlines() == [
        "param doc",
        "multi line",
    ]
    assert doc.flags == {"optional": ["-o", "--opt"]}


def test_generated_parser():
    from xonsh.completers._aliases import CompleterAlias

    alias = CompleterAlias()

    assert alias.parser.description

    positionals = alias.parser._get_positional_actions()
    add_cmd = positionals[0].choices["add"]
    assert "Add a new completer" in add_cmd.description
    assert (
        alias.parser.format_usage()
        == "usage: completer [-h] {add,remove,rm,list,ls,complete} ...\n"
    )
    assert add_cmd.format_usage() == "usage: completer add [-h] name func [pos]\n"


def test_parser_hooking():
    from xonsh.history.main import HistoryAlias

    alias = HistoryAlias()

    parser, _ = cli_utils.ArgparseCompleter.get_parser(alias.parser, ["show"])
    assert parser._get_positional_actions()[0].choices == (
        "session",
        "xonsh",
        "all",
        "zsh",
        "bash",
    )


def test_parser_default_func(mocker):
    import xonsh.xontribs as xx

    alias = xx.XontribAlias()

    def func():
        return True

    mocker.patch.object(xx, "xontribs_list", func)
    assert alias([]) is True
