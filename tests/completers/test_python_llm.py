"""Path-vs-operator completion in ``xonsh/completers/python.py``.

For an unknown command, the Python completer splits ``--home=/`` on ``=`` and
used to offer operator tokens (``/`` ``//`` ``/=`` ``//=``) for the trailing
``/``.  Being exclusive and running before the path completer, those tokens
shadowed path completion.  A value that begins with a path separator must not
get operator completions, so the path completer can list the directory.
"""

import os
from collections import OrderedDict
from types import SimpleNamespace

import pytest

from xonsh.completers.init import default_completers
from xonsh.completers.python import complete_python
from xonsh.completers.tools import (
    contextual_completer,
    is_exclusive_completer,
    non_exclusive_completer,
)
from xonsh.events import events
from xonsh.parsers.completion_context import CompletionContext
from xonsh.pytest.tools import skip_if_on_windows


@pytest.fixture(autouse=True)
def xonsh_execer_autouse(xession, xonsh_execer):
    return xonsh_execer


def _values(result):
    if not result:
        return set()
    comps = result[0] if isinstance(result, tuple) else result
    return {str(c).strip() for c in comps}


@pytest.mark.parametrize(
    "line",
    ["qwewqe --home=/", "qwewqe if=/", "qwewqe --home=~"],
    ids=["dashed-opt", "bare-opt", "tilde"],
)
def test_python_skips_operators_for_path_value(line, completion_context_parse):
    """A path value after ``=`` must not yield Python operator tokens."""
    res = complete_python(completion_context_parse(line, len(line)))
    # tokens that collide with a leading '/' or '~'
    assert _values(res) & {"/", "//", "/=", "//=", "~"} == set()


@pytest.mark.parametrize("line", ["5 /", "x = /"])
def test_python_keeps_operators_for_real_expression(line, completion_context_parse):
    """Genuine operator completion (``/`` from an expression) is preserved.

    Here ``/`` is the whole prefix (from the space split), so the first
    completion attempt already matches operators and the ``=`` fallback that
    the fix guards is never reached.
    """
    res = complete_python(completion_context_parse(line, len(line)))
    assert {"/", "//", "/=", "//="} <= _values(res)


@skip_if_on_windows
def test_path_completion_not_shadowed_end_to_end(completer_obj):
    """Full pipeline: ``app --home=/<TAB>`` yields paths, not ``/=``."""
    line = "qwewqe --home=/"
    comps, lprefix = completer_obj.complete_line(line)
    vals = {str(c).rstrip() for c in comps}

    # operator tokens no longer shadow the path completer ...
    assert not (vals & {"/", "//", "/=", "//="})
    # ... and the root directory is listed, replacing only the typed '/'.
    assert lprefix == 1
    assert vals, "expected root path completions"
    assert all(v.startswith("/") for v in vals)
    assert any(v.endswith(os.sep) for v in vals)


@pytest.fixture(params=["prefix", "substring_tier"])
def python_path_session(request, xession, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "lest.txt").touch()
    xession.env.update(
        PATH=[],
        XONSH_COMPLETER_MODE=request.param,
        COMPLETION_QUERY_LIMIT=0,
        COMMANDS_CACHE_SAVE_INTERMEDIATE=False,
    )
    xession.ctx["lemon"] = 1
    monkeypatch.setattr(
        xession, "_completers", default_completers(xession.commands_cache)
    )
    return xession


def test_unknown_command_keeps_python_and_file_candidates(
    python_path_session, completer_obj
):
    context = completer_obj.parse("somecmd le", ctx=python_path_session.ctx)

    completions, _ = completer_obj.complete_from_context(context)

    values = {str(comp): comp.prefix_len for comp in completions}
    assert values["lemon"] == values["len"] == 2
    assert "lest.txt " in values, "Python results must not hide the matching file"
    assert values["lest.txt "] == 2


@pytest.mark.parametrize(
    "line",
    [
        "somecmd arg le",
        "somecmd dir/file le",
        "somecmd 12 le",
        'somecmd "arg" le',
        "somecmd --opt=le",
        "somecmd --opt=x le",
    ],
)
def test_supported_unknown_command_arguments(line, python_path_session, completer_obj):
    context = completer_obj.parse(line, ctx=python_path_session.ctx)

    completions, _ = completer_obj.complete_from_context(context)

    assert {"lemon", "len", "lest.txt "} <= set(completions)


@pytest.mark.parametrize(
    "line",
    [
        "x = le",
        "x=le",
        "1 + le",
        "a + le",
        "a - le",
        "a and le",
        "a is le",
        "a not in le",
        '"less" in le',
        "somecmd @(le",
        "unknownfn(le",
        "unknownfn (le",
        "unknownfn (a le",
        "unknownfn (x, le",
        "(le",
        "(x + le",
        "[le",
        "{le",
        "x = (le",
        "x = fn (le",
        "x += le",
        "x := le",
        "x: le",
        "return le",
        "await le",
        "raise le",
        "yield le",
        "assert le",
        "if le",
        "for x in le",
        "lambda x: le",
        "match le",
        "case le",
        "type Foo = le",
        "len le",
        "somecmd -q le",
        "some-cmd le",
        "somecmd ./dir le",
        "somecmd foo; somecmd = le",
        "somecmd foo | somecmd + le",
        "somecmd foo and somecmd + le",
        "somecmd foo or somecmd + le",
        "somecmd foo && somecmd + le",
        "somecmd foo # le",
        "somecmd foo\nsomecmd = le",
        "somecmd --opt=foo; somecmd = le",
    ],
)
def test_python_and_conservative_boundaries_stay_exclusive(
    line, python_path_session, completer_obj
):
    context = completer_obj.parse(line, ctx=python_path_session.ctx)

    completions, _ = completer_obj.complete_from_context(context)

    assert "lemon" in completions
    assert "lest.txt " not in completions
    assert is_exclusive_completer(complete_python, context)


@pytest.mark.parametrize("line", ["x = le +", "a + le +"])
def test_unfinished_operator_expression_stays_exclusive(
    line, python_path_session, completer_obj, tmp_path
):
    (tmp_path / "+file").touch()
    context = completer_obj.parse(line, ctx=python_path_session.ctx)

    completions, _ = completer_obj.complete_from_context(context)

    assert "+" in completions
    assert "+file " not in completions


@pytest.mark.parametrize(
    "line",
    [
        "obj.le",
        "somecmd @(obj.le",
        "x = obj.le",
        "somecmd obj.le",
        "somecmd arg obj.le",
        "somecmd --opt=obj.le",
    ],
)
def test_attribute_completion_does_not_acquire_files(
    line, python_path_session, completer_obj, tmp_path
):
    python_path_session.ctx["obj"] = SimpleNamespace(length=1)
    (tmp_path / "obj.length.txt").touch()
    context = completer_obj.parse(line, ctx=python_path_session.ctx)

    completions, _ = completer_obj.complete_from_context(context)

    assert "obj.length" in completions
    assert "obj.length.txt " not in completions
    attribute = next(comp for comp in completions if str(comp) == "obj.length")
    assert attribute.prefix_len == len("obj.le")
    assert not attribute.append_space
    assert attribute.append_closing_quote
    assert line[: -attribute.prefix_len] + str(attribute) == line[:-6] + "obj.length"


@pytest.mark.parametrize(
    "line",
    [
        "somecmd pyproject.to",
        "somecmd arg pyproject.to",
        "somecmd --opt=pyproject.to",
    ],
)
def test_attribute_collision_keeps_python_insertion(
    line, python_path_session, completer_obj, tmp_path
):
    python_path_session.ctx["pyproject"] = SimpleNamespace(toml=1)
    (tmp_path / "pyproject.toml").touch()
    context = completer_obj.parse(line, ctx=python_path_session.ctx)

    completions, length = completer_obj.complete_from_context(context)

    assert [
        (
            str(comp),
            comp.prefix_len,
            comp.append_space,
            comp.append_closing_quote,
            comp.provider,
        )
        for comp in completions
    ] == [("pyproject.toml", 12, False, True, None)]
    assert length == 12
    assert line[: -completions[0].prefix_len] + str(completions[0]) == (
        line[:-12] + "pyproject.toml"
    )


@pytest.mark.parametrize("line", ["import zz6499", "from os import zz6499"])
def test_import_fallback_does_not_acquire_files(
    line, python_path_session, completer_obj, tmp_path
):
    python_path_session.ctx["zz6499_python"] = 1
    (tmp_path / "zz6499_file.txt").touch()
    context = completer_obj.parse(line, ctx=python_path_session.ctx)

    completions, _ = completer_obj.complete_from_context(context)

    assert "zz6499_python" in completions
    assert "zz6499_file.txt " not in completions


@pytest.mark.parametrize("kind", ["executable", "alias", "unknown"])
@pytest.mark.parametrize("shadow", [False, True])
def test_command_and_python_name_precedence(
    kind, shadow, python_path_session, completer_obj, tmp_path
):
    name = "somecmd"
    if kind == "executable":
        bindir = tmp_path / "bin"
        bindir.mkdir()
        executable = bindir / (name + ".exe" if os.name == "nt" else name)
        executable.touch()
        executable.chmod(0o755)
        python_path_session.env["PATH"] = [str(bindir)]
    if kind == "alias":
        python_path_session.aliases[name] = ["unavailable_target"]
    if shadow:
        python_path_session.ctx[name] = 1
    context = completer_obj.parse(f"{name} le", ctx=python_path_session.ctx)

    completions, _ = completer_obj.complete_from_context(context)

    assert ("lemon" in completions) == (shadow or kind == "unknown")
    assert ("lest.txt " in completions) == (not shadow)


def test_mixed_candidates_keep_individual_insertion_lengths(
    python_path_session, completer_obj, tmp_path
):
    (tmp_path / "--opt=lest.txt").touch()
    line = "somecmd --opt=le"
    context = completer_obj.parse(line, ctx=python_path_session.ctx)

    completions, length = completer_obj.complete_from_context(context)

    values = {str(comp): comp for comp in completions}
    assert values["lemon"].prefix_len == 2
    assert values["--opt=lest.txt "].prefix_len == length == 8
    assert {
        line[: -comp.prefix_len] + str(comp)
        for comp in (values["lemon"], values["--opt=lest.txt "])
    } == {"somecmd --opt=lemon", "somecmd --opt=lest.txt "}


@pytest.mark.parametrize(
    "line,cursor,length,inserted",
    [
        ("somecmd ./le", 12, 4, "somecmd ./lest.txt "),
        ('somecmd "le', 11, 3, 'somecmd "lest.txt" '),
        ('somecmd "le"', 12, 4, 'somecmd "lest.txt" '),
        ('somecmd "le"', 11, 3, 'somecmd "lest.txt"'),
        ("somecmd 'le", 11, 3, "somecmd 'lest.txt' "),
        ("somecmd le", 10, 2, "somecmd 'le space.txt' "),
    ],
)
def test_path_insertion_preserves_quotes_and_relative_prefixes(
    line, cursor, length, inserted, python_path_session, completer_obj, tmp_path
):
    (tmp_path / "le space.txt").touch()
    context = completer_obj.parse(line, cursor, python_path_session.ctx)

    completions, _ = completer_obj.complete_from_context(context)

    assert (length, inserted) in {
        (comp.prefix_len, line[: cursor - comp.prefix_len] + str(comp) + line[cursor:])
        for comp in completions
    }


@pytest.mark.parametrize("position", ["before", "after"])
@pytest.mark.parametrize("outcome", ["exclusive", "stop", "empty", "blank", "none"])
def test_registered_stops_control_python_and_path(
    position, outcome, python_path_session, completer_obj, monkeypatch
):
    @contextual_completer
    def sentinel(context):
        if outcome == "stop":
            raise StopIteration
        return {
            "exclusive": {"SENTINEL"},
            "empty": set(),
            "blank": {"  "},
            "none": None,
        }[outcome]

    called = []

    @events.on_completer_filter
    def record(completer, **kwargs):
        called.append(completer)

    providers = list(python_path_session.completers.items())
    index = [name for name, _ in providers].index("python") + (position == "after")
    providers.insert(index, ("sentinel", sentinel))
    monkeypatch.setattr(python_path_session, "_completers", OrderedDict(providers))
    context = completer_obj.parse("somecmd le", ctx=python_path_session.ctx)

    completions, _ = completer_obj.complete_from_context(context)

    stops = outcome in {"exclusive", "stop"}
    assert ("path" in called) == (not stops)
    assert ("lemon" in completions) == (position == "after" or not stops)
    assert ("SENTINEL" in completions) == (outcome == "exclusive")
    assert ("lest.txt " in completions) == (not stops)


@pytest.mark.parametrize("control", ["veto", "replacement"])
def test_registered_path_is_respected(
    control, python_path_session, completer_obj, monkeypatch
):
    if control == "veto":

        @events.on_completer_filter
        def veto(completer, **kwargs):
            if completer == "path":
                return False

    else:

        @contextual_completer
        def replacement(context):
            return {"REGISTERED_PATH"}

        monkeypatch.setitem(python_path_session.completers, "path", replacement)
    context = completer_obj.parse("somecmd le", ctx=python_path_session.ctx)

    completions, _ = completer_obj.complete_from_context(context)

    assert "lemon" in completions
    assert "lest.txt " not in completions
    assert ("REGISTERED_PATH" in completions) == (control == "replacement")


def test_attached_alias_completer_still_wins(python_path_session, completer_obj):
    def alias(args):
        pass

    alias.xonsh_complete = lambda **kwargs: {"le_alias"}
    python_path_session.aliases["somecmd"] = alias
    python_path_session.ctx["somecmd"] = 1
    context = completer_obj.parse("somecmd le", ctx=python_path_session.ctx)

    completions, _ = completer_obj.complete_from_context(context)

    assert set(completions) == {"le_alias"}


@pytest.mark.parametrize("marker", [None, False, True])
def test_existing_exclusivity_markers_are_unchanged(marker):
    def provider():
        pass

    if marker is not None:
        provider.non_exclusive = marker

    assert is_exclusive_completer(provider) == (not marker)
    assert is_exclusive_completer(provider, CompletionContext()) == (not marker)


def test_bare_non_exclusive_decorator_preserves_identity():
    def provider():
        pass

    assert non_exclusive_completer(provider) is provider
    assert not is_exclusive_completer(provider)


@pytest.mark.parametrize("decision", [False, True])
@pytest.mark.parametrize("with_context", [False, True])
def test_conditional_exclusivity_is_request_local(decision, with_context):
    calls = []

    def predicate(context):
        calls.append(context)
        return decision

    def provider():
        pass

    decorated = non_exclusive_completer(when=predicate)(provider)
    context = CompletionContext() if with_context else None

    exclusive = is_exclusive_completer(decorated, context)

    assert decorated is provider
    assert exclusive == (not with_context or not decision)
    assert calls == ([context] if with_context else [])
    assert provider.non_exclusive is predicate
