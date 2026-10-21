"""CLI contracts for recorded working-directory history filtering."""

import io
import os

import pytest

from xonsh.history.json import JsonHistory
from xonsh.history.main import HistoryAlias
from xonsh.history.sqlite import SqliteHistory


def flush_history(hist):
    thread = hist.flush()
    if thread is not None:
        thread.join()


def run_history(argv):
    out, err = io.StringIO(), io.StringIO()
    HistoryAlias()(argv, stdout=out, stderr=err)
    assert not err.getvalue(), err.getvalue()
    return out.getvalue()


@pytest.fixture(params=[JsonHistory, SqliteHistory], ids=["json", "sqlite"])
def recorded_history(request, tmp_path, xession, monkeypatch):
    xession.env["XONSH_DATA_DIR"] = str(tmp_path)
    xession.env["HISTCONTROL"] = set()
    target = str(tmp_path / "work space")
    backend = request.param

    def make(session):
        filename = (
            tmp_path / "history.sqlite"
            if backend is SqliteHistory
            else tmp_path / "history_json" / f"xonsh-{session}.json"
        )
        filename.parent.mkdir(exist_ok=True)
        return backend(
            filename=str(filename), sessionid=session, gc=False, save_cwd=True
        )

    old = make("old")
    old.append({"inp": "old", "ts": (10, 11), "rtn": 0, "cwd": target})
    flush_history(old)
    hist = make("current")
    for index, cwd in enumerate([target, target + "/child", target, None]):
        cmd = {"inp": f"cmd{index}", "ts": (20 + index, 21 + index), "rtn": 0}
        if cwd is not None:
            cmd["cwd"] = cwd
        hist.append(cmd)
    flush_history(hist)
    hist.save_cwd = False
    hist.append({"inp": "unsaved", "ts": (30, 31), "rtn": 0, "cwd": target})
    monkeypatch.setattr(xession, "history", hist)
    yield hist, target
    flush_history(hist)


def test_native_cwd_cli(recorded_history):
    _, target = recorded_history
    assert run_history(["show", "--cwd", target]) == "cmd0\ncmd2\n"
    assert run_history(["show", "all", "--cwd", target]) == "old\ncmd0\ncmd2\n"


def test_native_scope_and_composition(recorded_history):
    hist, target = recorded_history
    assert run_history(["--cwd", target]) == "cmd0\ncmd2\n"
    assert run_history(["show", "xonsh", "--cwd", target]) == "old\ncmd0\ncmd2\n"
    assert run_history(["show", "0:2", "--cwd", target, "-n"]) == "0: cmd0\n"
    for slices, expected in [
        (["2"], "2: cmd2\n"),
        (["::2"], "0: cmd0\n2: cmd2\n"),
        (["::-1"], "2: cmd2\n0: cmd0\n"),
        (["0:3", "2:3"], "0: cmd0\n2: cmd2\n2: cmd2\n"),
    ]:
        assert run_history(["show", *slices, "--cwd", target, "-n"]) == expected
    assert (
        run_history(["show", "-3:", "--cwd", target, "-n", "-r", "-0"]) == "2: cmd2\0"
    )
    assert (
        run_history(["show", "--cwd", target, "--start-time", "20", "-T", "22"])
        == "cmd0\n"
    )
    assert (
        run_history(["show", "--cwd", target, "--start-time", "22", "-T", "23"])
        == "cmd2\n"
    )
    assert run_history(["show", "--cwd", target + "-sibling"]) == ""
    assert "unsaved" in run_history(["show"])
    flush_history(hist)
    assert run_history(["show", "--cwd", target]) == "cmd0\ncmd2\n"


def test_native_paths(recorded_history, monkeypatch, tmp_path):
    _, target = recorded_history
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    for query in ["work space", "./work space/../work space/", "~/work space"]:
        assert run_history(["show", "--cwd", query]) == "cmd0\ncmd2\n"
    assert run_history(["show", "--cwd", "$HOME/work space"]) == ""
    expected = (
        "cmd0\ncmd2\n"
        if os.path.normcase(target.upper()) == os.path.normcase(target)
        else ""
    )
    assert run_history(["show", "--cwd", target.upper()]) == expected
    link = tmp_path / "link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as err:
        if getattr(err, "winerror", None) != 1314:
            raise
        pytest.skip("Creating symlinks requires Windows privileges")
    assert run_history(["show", "--cwd", str(link)]) == ""


@pytest.mark.parametrize("flags", [["-t"], ["-n", "-t"], ["-0"]])
def test_native_output(recorded_history, flags):
    import datetime

    from xonsh.tools import format_datetime

    _, target = recorded_history
    expected = []
    for index in [0, 2]:
        prefix = f"{index}:" if "-n" in flags else ""
        if "-t" in flags:
            prefix += (
                f"({format_datetime(datetime.datetime.fromtimestamp(20 + index))}) "
            )
        expected.append(f"{prefix}cmd{index}")
    end = "\0" if "-0" in flags else "\n"
    assert run_history(["show", "--cwd", target, *flags]) == end.join(expected) + end


def test_json_metadata_opt_in(recorded_history):
    hist, target = recorded_history
    if not isinstance(hist, JsonHistory):
        pytest.skip("JSON metadata contract")
    before = open(hist.filename, "rb").read()
    for newest in [False, True]:
        default = list(hist.items(newest_first=newest))
        expected = [{"inp": f"cmd{index}", "ts": 20 + index} for index in range(4)] + [
            {"inp": "unsaved", "ts": 30}
        ]
        assert default == (list(reversed(expected)) if newest else expected)
        assert all(list(item) == ["inp", "ts"] for item in default)
        rich = list(hist.items(newest_first=newest, include_cwd=True))
        assert [{key: item[key] for key in ["inp", "ts"]} for item in rich] == default
        assert next(item for item in rich if item["inp"] == "cmd0")["cwd"] == target
        assert next(item for item in rich if item["inp"] == "cmd3")["cwd"] is None
        assert next(item for item in rich if item["inp"] == "unsaved")["cwd"] is None
        all_default = list(hist.all_items(newest_first=newest))
        assert all(list(item) == ["inp", "ts"] for item in all_default)
        all_rich = list(hist.all_items(newest_first=newest, include_cwd=True))
        assert [
            {key: item[key] for key in ["inp", "ts"]} for item in all_rich
        ] == all_default
        assert list(hist.items(newest_first=newest)) == default
    assert open(hist.filename, "rb").read() == before


def test_old_backend_calls_and_unknown_cwd(xession, monkeypatch, tmp_path):
    from xonsh.history.dummy import DummyHistory

    calls = []

    class OldHistory:
        def items(self):
            calls.append("items")
            return iter(
                [{"inp": "known", "ts": 1, "cwd": str(tmp_path)}]
                + [
                    {"inp": "unknown", "ts": 2, "cwd": value}
                    for value in [None, "", 42]
                ]
            )

        def all_items(self, newest_first=False):
            calls.append(("all_items", newest_first))
            return self.items()

    monkeypatch.setattr(xession, "history", OldHistory())
    assert run_history(["show", "--cwd", str(tmp_path)]) == "known\n"
    assert run_history(["show", "all", "--cwd", str(tmp_path)]) == "known\n"
    assert run_history(["show"]).count("unknown") == 3
    assert calls == ["items", ("all_items", False), "items", "items"]
    monkeypatch.setattr(xession, "history", DummyHistory())
    assert "dummy" in run_history(["show"])
    assert run_history(["show", "all", "--cwd", str(tmp_path)]) == ""


def test_json_inherited_and_override(recorded_history, monkeypatch, xession):
    hist, target = recorded_history
    if not isinstance(hist, JsonHistory):
        pytest.skip("JSON method identity contract")

    class Inherited(JsonHistory):
        pass

    class Override(JsonHistory):
        def items(self):
            return iter([{"inp": "override", "ts": 1}])

        def all_items(self, newest_first=False):
            return self.items()

    monkeypatch.setattr(hist, "__class__", Inherited)
    assert run_history(["show", "all", "--cwd", target]) == "old\ncmd0\ncmd2\n"
    monkeypatch.setattr(hist, "__class__", Override)
    assert run_history(["show"]) == "override\n"
    assert run_history(["show", "--cwd", target]) == ""
    assert run_history(["show", "all", "--cwd", target]) == ""


@pytest.mark.parametrize("failure", ["late", "slice", "time", "path"])
def test_cwd_error_boundary(failure, xession, monkeypatch, tmp_path):
    class BrokenHistory:
        def flush(self, **kwargs):
            pass

        def items(self):
            yield {
                "inp": "first",
                "ts": "bad" if failure == "time" else 1,
                "cwd": str(tmp_path),
            }
            if failure == "late":
                raise ValueError("late failure")

    monkeypatch.setattr(xession, "history", BrokenHistory())
    out, err = io.StringIO(), io.StringIO()
    argv = ["show", "--cwd", str(tmp_path)]
    if failure == "slice":
        argv += ["::0"]
    elif failure == "time":
        argv += ["--start-time", "0"]
    elif failure == "path":
        from xonsh.history import main

        monkeypatch.setattr(main.xt, "expanduser_abs_path", lambda value: 1 / 0)
    result = HistoryAlias()(argv, stdout=out, stderr=err)
    assert result is None
    assert out.getvalue() == ""
    assert err.getvalue().startswith("history: error: ")


def test_help_and_imported_history(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        HistoryAlias()(["show", "--help"])
    assert exc.value.code == 0
    assert "--cwd CWD" in capsys.readouterr().out
    with pytest.raises(SystemExit) as exc:
        HistoryAlias()(["show", "--cwd"])
    assert exc.value.code == 2
    source = tmp_path / "imported"
    source.write_text("echo temporary\n")
    assert run_history(["show", "bash", "-l", str(source)]) == "echo temporary\n"
    assert (
        run_history(["show", "bash", "-l", str(source), "--cwd", str(tmp_path)]) == ""
    )


def test_json_default_does_not_read_cwd(recorded_history, monkeypatch):
    hist, _ = recorded_history
    if not isinstance(hist, JsonHistory):
        pytest.skip("JSON metadata contract")
    expected = list(hist.all_items())
    monkeypatch.setattr(hist, "cwds", None)
    assert list(hist.all_items()) == expected


def test_native_empty_and_relative_recorded_cwd(
    recorded_history, monkeypatch, tmp_path
):
    hist, _ = recorded_history
    hist.save_cwd = True
    hist.append({"inp": "empty", "ts": (40, 41), "rtn": 0, "cwd": ""})
    hist.append({"inp": "relative", "ts": (42, 43), "rtn": 0, "cwd": "relative"})
    flush_history(hist)
    monkeypatch.chdir(tmp_path)
    assert run_history(["show", "--cwd", ""]) == ""
    assert run_history(["show", "--cwd", str(tmp_path / "relative")]) == "relative\n"


def test_history_not_ready(xession, monkeypatch, capsys):
    monkeypatch.setattr(xession, "history", None)
    HistoryAlias()(["show", "--cwd", "/temporary"])
    assert "history backend is not ready" in capsys.readouterr().err
