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
        "    multi line",
    ]
