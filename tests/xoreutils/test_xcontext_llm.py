"""Tests for ``xonsh.xoreutils.xcontext``."""

import io
import json
import os
import subprocess
from unittest import mock

import pytest

from xonsh.platform import ON_WINDOWS
from xonsh.xoreutils import xcontext

# ---------------------------------------------------------------------------
# _resolve_one — Windows PATHEXT fallback via locate_relative_path
# ---------------------------------------------------------------------------


def test_resolve_one_bare_script_resolves_to_exe_on_windows(tmp_path, xession):
    """Windows-only: ``C:\\...\\Scripts\\xonsh`` must resolve to
    ``xonsh.exe`` so ``xxonsh`` isn't red and matches the PATH row.
    """
    if not ON_WINDOWS:
        pytest.skip("Windows-only — relies on PATHEXT executable check")
    scripts = tmp_path / "Scripts"
    scripts.mkdir()
    real = scripts / "xonsh.exe"
    real.write_bytes(b"")
    os.chmod(str(real), 0o755)
    xession.env["PATHEXT"] = [".EXE", ".BAT", ".CMD", ".COM"]

    bare = str(scripts / "xonsh")
    assert not os.path.exists(bare)

    resolved, bad = xcontext._resolve_one(bare, resolve=True)
    assert os.path.samefile(resolved, str(real))
    assert bad is False


def test_resolve_one_bare_script_no_resolve_still_probes(tmp_path, xession):
    """With ``--no-resolve`` the ext probe still runs, so the row
    isn't mistakenly flagged as missing just because symlink
    resolution was disabled.
    """
    if not ON_WINDOWS:
        pytest.skip("Windows-only — relies on PATHEXT executable check")
    scripts = tmp_path / "Scripts"
    scripts.mkdir()
    real = scripts / "xonsh.exe"
    real.write_bytes(b"")
    os.chmod(str(real), 0o755)
    xession.env["PATHEXT"] = [".EXE"]

    bare = str(scripts / "xonsh")
    resolved, bad = xcontext._resolve_one(bare, resolve=False)
    assert os.path.samefile(resolved, str(real))
    assert bad is False


def test_resolve_one_existing_file_untouched(tmp_path, xession):
    """If the value already exists on disk, we keep it as-is (this is
    what preserves the ``__main__.py`` entry-point case used by
    ``python -m xonsh``).
    """
    entry = tmp_path / "xonsh"
    entry.mkdir()
    main_py = entry / "__main__.py"
    main_py.write_text("")
    xession.env["PATHEXT"] = [".EXE"]

    resolved, bad = xcontext._resolve_one(str(main_py), resolve=True)
    assert resolved == str(main_py)
    # ``__main__.py`` is never +x but is treated as good by the
    # special case in ``_is_executable_file``.
    assert bad is False


def test_resolve_one_missing_path_still_bad(tmp_path, xession):
    """Completely missing path stays flagged."""
    xession.env["PATHEXT"] = [".EXE"]
    missing = str(tmp_path / "ghost")
    _, bad = xcontext._resolve_one(missing, resolve=True)
    assert bad is True


# ---------------------------------------------------------------------------
# _get_version — error handling for unexecutable $PATH entries
# ---------------------------------------------------------------------------


def test_get_version_spawn_error_returns_not_ok(xession):
    """An ``OSError`` from :func:`subprocess.run` (e.g. the Windows
    Store ``python.exe`` App Execution Alias raising WinError 1920)
    must be swallowed and signalled via ``ok=False`` — no traceback
    leaks to stderr.
    """
    with mock.patch.object(
        xcontext.subprocess,
        "run",
        side_effect=OSError(1920, "The file cannot be accessed by the system"),
    ):
        version, ok = xcontext._get_version("/fake/python")
    assert version == ""
    assert ok is False


def test_get_version_spawn_error_raises_when_debug(xession):
    """With ``$DEBUG`` set, the error is re-raised so developers can
    see the full stack trace.
    """
    xession.env["DEBUG"] = True
    with mock.patch.object(
        xcontext.subprocess,
        "run",
        side_effect=OSError(1920, "The file cannot be accessed by the system"),
    ):
        with pytest.raises(OSError):
            xcontext._get_version("/fake/python")


def test_get_version_happy_path(xession):
    """Successful spawn returns ``(trimmed_stdout, True)``."""
    fake_completed = subprocess.CompletedProcess(
        args=["python", "--version"],
        returncode=0,
        stdout="Python 3.13.3\n",
        stderr="",
    )
    with mock.patch.object(xcontext.subprocess, "run", return_value=fake_completed):
        version, ok = xcontext._get_version("/usr/bin/python")
    assert version == "Python 3.13.3"
    assert ok is True


def test_get_version_strips_pip_from_suffix(xession):
    """``pip --version`` prints ``pip 24.0 from /path/pip (python 3.13)``
    — the `` from `` suffix is stripped so only ``pip 24.0`` remains.
    """
    fake_completed = subprocess.CompletedProcess(
        args=["pip", "--version"],
        returncode=0,
        stdout="pip 24.0 from /site-packages/pip (python 3.13)\n",
        stderr="",
    )
    with mock.patch.object(xcontext.subprocess, "run", return_value=fake_completed):
        version, ok = xcontext._get_version("/usr/bin/pip")
    assert version == "pip 24.0"
    assert ok is True


def test_get_version_accepts_list_binary(xession):
    """Binary can be a list (e.g. ``xpip = [python, -m, pip]``) — the
    ``--version`` arg is appended to the list.
    """
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(
            args=cmd, returncode=0, stdout="pip 24.0", stderr=""
        )

    with mock.patch.object(xcontext.subprocess, "run", side_effect=fake_run):
        version, ok = xcontext._get_version(["/usr/bin/python", "-m", "pip"])
    assert captured["cmd"] == ["/usr/bin/python", "-m", "pip", "--version"]
    assert version == "pip 24.0"
    assert ok is True


def test_get_version_falls_back_to_stderr(xession):
    """If stdout is empty, use stderr (older python versions printed
    ``--version`` output there).
    """
    fake_completed = subprocess.CompletedProcess(
        args=["python", "--version"],
        returncode=0,
        stdout="",
        stderr="Python 2.7.18\n",
    )
    with mock.patch.object(xcontext.subprocess, "run", return_value=fake_completed):
        version, ok = xcontext._get_version("/usr/bin/python")
    assert version == "Python 2.7.18"
    assert ok is True


# ---------------------------------------------------------------------------
# xcontext_main — [Current environment] section visibility
# ---------------------------------------------------------------------------


def _run_xcontext_main(xession):
    """Run ``xcontext_main`` with a captured stdout and all subprocess
    and path-lookup side effects stubbed out. Returns the stdout text.
    """
    buf = io.StringIO()
    fake_completed = subprocess.CompletedProcess(
        args=["python", "--version"],
        returncode=0,
        stdout="Python 3.13.3\n",
        stderr="",
    )
    xession.aliases["xpip"] = ["/fake/python", "-m", "pip"]
    with (
        mock.patch.object(xcontext.subprocess, "run", return_value=fake_completed),
        mock.patch.object(xcontext, "locate_executable", return_value="/fake/bin"),
        mock.patch.object(
            xcontext, "_resolve_path", side_effect=lambda v, r: (v, False)
        ),
        mock.patch("xonsh.main.get_current_xonsh", return_value="/fake/xonsh"),
        mock.patch.object(
            xcontext,
            "print_color",
            side_effect=lambda s, file=None: print(s, file=file),
        ),
    ):
        xcontext.xcontext_main(_stdout=buf)
    return buf.getvalue()


def test_current_environment_hidden_when_empty(xession):
    """With no CONDA_DEFAULT_ENV / VIRTUAL_ENV set, the whole
    ``[Current environment]`` section (header + blank-line separator)
    must not appear.
    """
    xession.env.pop("CONDA_DEFAULT_ENV", None)
    xession.env.pop("VIRTUAL_ENV", None)
    out = _run_xcontext_main(xession)
    assert "[Current environment]" not in out
    # And no trailing blank line before a missing header — the last
    # section must be ``[Current commands environment]``.
    assert out.rstrip().endswith("/fake/bin") or "/fake/bin" in out.splitlines()[-1]


def test_current_environment_shown_when_virtualenv_set(xession):
    xession.env.pop("CONDA_DEFAULT_ENV", None)
    xession.env["VIRTUAL_ENV"] = "/tmp/my-venv"
    out = _run_xcontext_main(xession)
    assert "[Current environment]" in out
    assert "VIRTUAL_ENV" in out
    assert "/tmp/my-venv" in out
    assert "CONDA_DEFAULT_ENV" not in out


def test_current_environment_shown_when_conda_set(xession):
    xession.env["CONDA_DEFAULT_ENV"] = "myenv"
    xession.env.pop("VIRTUAL_ENV", None)
    out = _run_xcontext_main(xession)
    assert "[Current environment]" in out
    assert "CONDA_DEFAULT_ENV" in out
    assert "myenv" in out
    assert "VIRTUAL_ENV" not in out


def test_resolve_path_list_head_uses_pathext_probe(tmp_path, xession):
    """List-valued aliases (``xpip = [python, -m, pip]``) have only
    their head element probed — trailing args are passed through
    unchanged.
    """
    if not ON_WINDOWS:
        pytest.skip("Windows-only — relies on PATHEXT executable check")
    scripts = tmp_path / "Scripts"
    scripts.mkdir()
    real = scripts / "python.exe"
    real.write_bytes(b"")
    os.chmod(str(real), 0o755)
    xession.env["PATHEXT"] = [".EXE"]

    bare = str(scripts / "python")
    resolved, bad = xcontext._resolve_path([bare, "-m", "pip"], resolve=True)
    assert os.path.samefile(resolved[0], str(real))
    assert resolved[1:] == ["-m", "pip"]
    assert bad is False


# ---------------------------------------------------------------------------
# xcontext_main — --json output mode
# ---------------------------------------------------------------------------


def _run_xcontext_json(xession, locate=None):
    """Run ``xcontext_main(as_json=True)`` and return the parsed JSON.

    ``locate`` overrides the per-name return value of ``locate_executable``;
    pass a dict like ``{"xonsh": "/x", "uv": None}`` to simulate names
    that are missing from ``$PATH``. Unspecified names default to
    ``"/fake/" + name``.
    """
    buf = io.StringIO()
    locate_map = {
        cmd: f"/fake/{cmd}" for cmd in ("xonsh", "python", "pip", "pytest", "uv")
    }
    if locate:
        locate_map.update(locate)
    xession.aliases["xpip"] = ["/fake/python", "-m", "pip"]
    with (
        mock.patch.object(
            xcontext, "locate_executable", side_effect=lambda c: locate_map.get(c)
        ),
        mock.patch.object(
            xcontext, "_resolve_path", side_effect=lambda v, r: (v, False)
        ),
        mock.patch("xonsh.main.get_current_xonsh", return_value="/fake/xonsh"),
    ):
        rc = xcontext.xcontext_main(as_json=True, _stdout=buf)
    assert rc == 0
    return json.loads(buf.getvalue()), buf.getvalue()


def test_json_output_has_expected_top_level_keys(xession):
    xession.env.pop("CONDA_DEFAULT_ENV", None)
    xession.env.pop("VIRTUAL_ENV", None)
    report, _ = _run_xcontext_json(xession)
    assert set(report) == {"session", "commands", "env"}


def test_json_session_carries_xpython_xxonsh_xpip(xession):
    """``session`` joins list-valued ``xpip`` with spaces — same flat
    string the colored output shows for the ``xpip:`` row.
    """
    xession.env.pop("CONDA_DEFAULT_ENV", None)
    xession.env.pop("VIRTUAL_ENV", None)
    report, _ = _run_xcontext_json(xession)
    assert report["session"] == {
        "xxonsh": "/fake/xonsh",
        "xpython": mock.ANY,  # sys.executable, untouched by stubbed _resolve_path
        "xpip": "/fake/python -m pip",
    }
    assert isinstance(report["session"]["xpython"], str)


def test_json_commands_includes_all_probed_names(xession):
    """``commands`` always lists every probed name (xonsh/python/pip/
    pytest/uv) so consumers don't have to special-case missing keys.
    """
    xession.env.pop("CONDA_DEFAULT_ENV", None)
    xession.env.pop("VIRTUAL_ENV", None)
    report, _ = _run_xcontext_json(xession)
    assert set(report["commands"]) == {"xonsh", "python", "pip", "pytest", "uv"}
    for cmd, path in report["commands"].items():
        assert path == f"/fake/{cmd}"


def test_json_commands_null_when_not_on_path(xession):
    """A name absent from ``$PATH`` shows up as JSON ``null``, not as a
    missing key — the schema is stable.
    """
    xession.env.pop("CONDA_DEFAULT_ENV", None)
    xession.env.pop("VIRTUAL_ENV", None)
    report, _ = _run_xcontext_json(xession, locate={"pytest": None, "uv": None})
    assert report["commands"]["pytest"] is None
    assert report["commands"]["uv"] is None
    assert report["commands"]["xonsh"] == "/fake/xonsh"


def test_json_env_empty_when_no_vars_set(xession):
    """``env`` mirrors the text section: only set variables appear, and
    the section is an empty object when none are."""
    xession.env.pop("CONDA_DEFAULT_ENV", None)
    xession.env.pop("VIRTUAL_ENV", None)
    report, _ = _run_xcontext_json(xession)
    assert report["env"] == {}


def test_json_env_includes_virtualenv_when_set(xession):
    xession.env.pop("CONDA_DEFAULT_ENV", None)
    xession.env["VIRTUAL_ENV"] = "/tmp/my-venv"
    report, _ = _run_xcontext_json(xession)
    assert report["env"] == {"VIRTUAL_ENV": "/tmp/my-venv"}


def test_json_env_includes_conda_when_set(xession):
    xession.env["CONDA_DEFAULT_ENV"] = "myenv"
    xession.env.pop("VIRTUAL_ENV", None)
    report, _ = _run_xcontext_json(xession)
    assert report["env"] == {"CONDA_DEFAULT_ENV": "myenv"}


def test_json_env_includes_both_when_set(xession):
    xession.env["CONDA_DEFAULT_ENV"] = "myenv"
    xession.env["VIRTUAL_ENV"] = "/tmp/my-venv"
    report, _ = _run_xcontext_json(xession)
    assert report["env"] == {
        "CONDA_DEFAULT_ENV": "myenv",
        "VIRTUAL_ENV": "/tmp/my-venv",
    }


def test_json_output_is_pretty_printed(xession):
    """Output is indented (indent=2) so it's human-readable in a
    terminal pipe and round-trips through ``json.loads``."""
    xession.env.pop("CONDA_DEFAULT_ENV", None)
    xession.env.pop("VIRTUAL_ENV", None)
    _, raw = _run_xcontext_json(xession)
    assert "\n  " in raw  # indented at least once
    assert raw.rstrip().endswith("}")


def test_json_skips_print_color_calls(xession):
    """JSON mode must not emit any ANSI escape sequences — the colored
    ``print_color`` path must be bypassed entirely so the output is safe
    to pipe to ``jq``.
    """
    xession.env.pop("CONDA_DEFAULT_ENV", None)
    xession.env.pop("VIRTUAL_ENV", None)
    with mock.patch.object(xcontext, "print_color") as pc:
        _, raw = _run_xcontext_json(xession)
    assert pc.call_count == 0
    assert "\x1b[" not in raw  # no ANSI escape sequences
