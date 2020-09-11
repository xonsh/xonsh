"""Tests for the Jedi completer xontrib"""
import sys
import pytest
import builtins
import importlib
from unittest.mock import MagicMock, call

from xonsh.xontribs import find_xontrib
from xonsh.completers.tools import RichCompletion


@pytest.fixture
def jedi_mock(monkeypatch):
    jedi_mock = MagicMock()
    jedi_mock.__version__ = "0.16.0"
    jedi_mock.Interpreter().complete.return_value = []
    jedi_mock.reset_mock()
    monkeypatch.setitem(sys.modules, "jedi", jedi_mock)
    yield jedi_mock


@pytest.fixture
def completer_mock(monkeypatch):
    completer_mock = MagicMock()

    # so that args will be passed
    def comp(args):
        completer_mock(args)

    monkeypatch.setitem(builtins.aliases, "completer", comp)
    yield completer_mock


@pytest.fixture
def jedi_xontrib(monkeypatch, source_path, jedi_mock, completer_mock):
    monkeypatch.syspath_prepend(source_path)
    spec = find_xontrib("jedi")
    yield importlib.import_module(spec.name)
    del sys.modules[spec.name]


def test_completer_added(jedi_xontrib, completer_mock):
    assert completer_mock.call_args_list == [
        call(["remove", "python_mode"]),
        call(["add", "jedi_python", "complete_jedi", "<python"]),
        call(["remove", "python"]),
    ]


@pytest.mark.parametrize(
    "prefix, line, start, end, ctx", [("x", "10 + x", 5, 6, {}),], ids="x"
)
@pytest.mark.parametrize("version", ["new", "old"])
def test_jedi_api(jedi_xontrib, jedi_mock, version, prefix, line, start, end, ctx):
    if version == "old":
        jedi_mock.__version__ = "0.15.0"
        jedi_mock.Interpreter().completions.return_value = []
        jedi_mock.reset_mock()

    jedi_xontrib.complete_jedi(prefix, line, start, end, ctx)

    extra_namespace = {"__xonsh__": builtins.__xonsh__}
    try:
        extra_namespace["_"] = _
    except NameError:
        pass
    namespaces = [{}, extra_namespace]

    if version == "new":
        assert jedi_mock.Interpreter.call_args_list == [call(line, namespaces)]
        assert jedi_mock.Interpreter().complete.call_args_list == [call(1, end)]
    else:
        assert jedi_mock.Interpreter.call_args_list == [
            call(line, namespaces, line=1, column=end)
        ]
        assert jedi_mock.Interpreter().completions.call_args_list == [call()]


def test_multiline(jedi_xontrib, jedi_mock, monkeypatch):
    shell_mock = MagicMock()
    complete_document = "xx = 1\n1 + x"
    shell_mock.shell_type = "prompt_toolkit"
    shell_mock.shell.pt_completer.current_document.text = complete_document
    shell_mock.shell.pt_completer.current_document.cursor_position_row = 1
    shell_mock.shell.pt_completer.current_document.cursor_position_col = 5
    monkeypatch.setattr(builtins.__xonsh__, "shell", shell_mock)
    jedi_xontrib.complete_jedi("x", "x", 0, 1, {})

    assert jedi_mock.Interpreter.call_args_list[0][0][0] == complete_document
    assert jedi_mock.Interpreter().complete.call_args_list == [
        call(2, 5)  # line (one-indexed), column (zero-indexed)
    ]


@pytest.mark.parametrize(
    "completion, rich_completion",
    [
        (
            # from jedi when code is 'x' and xx=3
            (
                "instance",
                "xx",
                "x",
                "int(x=None, /) -> int",
                ("instance", "instance int"),
            ),
            RichCompletion("x", display="xx", description="instance int"),
        ),
        (
            # from jedi when code is 'xx=3\nx'
            ("statement", "xx", "x", None, ("instance", "instance int")),
            RichCompletion("x", display="xx", description="instance int"),
        ),
        (
            # from jedi when code is 'x.' and x=3
            (
                "function",
                "from_bytes",
                "from_bytes",
                "from_bytes(bytes, byteorder, *, signed=False)",
                ("function", "def __get__"),
            ),
            RichCompletion(
                "from_bytes",
                display="from_bytes()",
                description="from_bytes(bytes, byteorder, *, signed=False)",
            ),
        ),
        (
            # from jedi when code is 'x=3\nx.'
            ("function", "imag", "imag", None, ("instance", "instance int")),
            RichCompletion("imag", display="imag", description="instance int"),
        ),
        (
            # from '(3).from_bytes(byt'
            ("param", "bytes=", "es=", None, ("instance", "instance Sequence")),
            RichCompletion("es=", display="bytes=", description="instance Sequence"),
        ),
        (
            # from 'x.from_bytes(byt' when x=3
            ("param", "bytes=", "es=", None, None),
            RichCompletion("es=", display="bytes=", description="param"),
        ),
        (
            # from 'import colle'
            ("module", "collections", "ctions", None, ("module", "module collections")),
            RichCompletion(
                "ctions", display="collections", description="module collections"
            ),
        ),
        (
            # from 'NameErr'
            (
                "class",
                "NameError",
                "or",
                "NameError(*args: object)",
                ("class", "class NameError"),
            ),
            RichCompletion(
                "or", display="NameError", description="NameError(*args: object)"
            ),
        ),
        (
            # from 'a["' when a={'name':None}
            ("string", '"name"', 'name"', None, None),
            RichCompletion('name"', display='"name"', description="string"),
        ),
        (
            # from 'open("/etc/pass'
            ("path", 'passwd"', 'wd"', None, None),
            RichCompletion('wd"', display='passwd"', description="path"),
        ),
        (
            # from 'cla'
            ("keyword", "class", "ss", None, None),
            RichCompletion("ss", display="class", description="keyword"),
        ),
    ],
)
def test_rich_completions(jedi_xontrib, jedi_mock, completion, rich_completion):
    comp_type, comp_name, comp_complete, sig, inf = completion
    comp_mock = MagicMock()
    comp_mock.type = comp_type
    comp_mock.name = comp_name
    comp_mock.complete = comp_complete
    if sig:
        sig_mock = MagicMock()
        sig_mock.to_string.return_value = sig
        comp_mock.get_signatures.return_value = [sig_mock]
    else:
        comp_mock.get_signatures.return_value = []
    if inf:
        inf_type, inf_desc = inf
        inf_mock = MagicMock()
        inf_mock.type = inf_type
        inf_mock.description = inf_desc
        comp_mock.infer.return_value = [inf_mock]
    else:
        comp_mock.infer.return_value = []

    jedi_xontrib.XONSH_SPECIAL_TOKENS = []
    jedi_mock.Interpreter().complete.return_value = [comp_mock]
    completions = jedi_xontrib.complete_jedi("", "", 0, 0, {})
    assert len(completions) == 1
    (ret_completion,) = completions
    assert isinstance(ret_completion, RichCompletion)
    assert ret_completion == rich_completion
    assert ret_completion.display == rich_completion.display
    assert ret_completion.description == rich_completion.description


def test_special_tokens(jedi_xontrib):
    assert (
        jedi_xontrib.complete_jedi("", "", 0, 0, {})
        == jedi_xontrib.XONSH_SPECIAL_TOKENS
    )
    assert jedi_xontrib.complete_jedi("@", "@", 0, 1, {}) == {"@", "@(", "@$("}
    assert jedi_xontrib.complete_jedi("$", "$", 0, 1, {}) == {"$[", "${", "$("}
