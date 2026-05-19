"""Tests for ``xonsh.xoreutils.xcontext``."""

import io
import json
import os
import re
import subprocess
import sys
from unittest import mock

import pytest

from xonsh.platform import ON_WINDOWS
from xonsh.xoreutils import xcontext

# ---------------------------------------------------------------------------
# _resolve_one — Windows PATHEXT fallback via locate_relative_path
# ---------------------------------------------------------------------------


def test_resolve_one_bare_script_resolves_to_exe_on_windows(tmp_path, xession):
    """Windows-only: ``C:\\...\\Scripts\\xonsh`` must resolve to
    ``xonsh.exe`` on the ``resolved`` side; the input is preserved on
    ``original`` so the colored renderer can show the unresolved form
    that the user actually typed.
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

    original, resolved, bad = xcontext._resolve_one(bare, resolve=True)
    assert original == bare
    assert os.path.samefile(resolved, str(real))
    assert bad is False


def test_resolve_one_bare_script_no_resolve_still_probes(tmp_path, xession):
    """With ``--no-resolve`` the ext probe still runs, so the row
    isn't mistakenly flagged as missing just because symlink
    resolution was disabled. The PATHEXT-resolved name is still on
    ``resolved``; the bare input stays on ``original``.
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
    original, resolved, bad = xcontext._resolve_one(bare, resolve=False)
    assert original == bare
    assert os.path.samefile(resolved, str(real))
    assert bad is False


def test_resolve_one_existing_file_untouched(tmp_path, xession):
    """If the value already exists on disk, we keep it as-is on both
    sides (this is what preserves the ``__main__.py`` entry-point case
    used by ``python -m xonsh``).
    """
    entry = tmp_path / "xonsh"
    entry.mkdir()
    main_py = entry / "__main__.py"
    main_py.write_text("")
    xession.env["PATHEXT"] = [".EXE"]

    original, resolved, bad = xcontext._resolve_one(str(main_py), resolve=True)
    assert original == str(main_py)
    assert resolved == str(main_py)
    # ``__main__.py`` is never +x but is treated as good by the
    # special case in ``_is_executable_file``.
    assert bad is False


def test_resolve_one_missing_path_still_bad(tmp_path, xession):
    """Completely missing path stays flagged."""
    xession.env["PATHEXT"] = [".EXE"]
    missing = str(tmp_path / "ghost")
    _, _, bad = xcontext._resolve_one(missing, resolve=True)
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
            xcontext, "_resolve_path", side_effect=lambda v, r: (v, v, False)
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


# ---------------------------------------------------------------------------
# xcontext_main — secondary ``name resolved:`` row
# ---------------------------------------------------------------------------


_COLOR_TOKENS_RE = re.compile(r"\{[A-Z_]+\}")


def _strip_color_tokens(text):
    """Drop the ``{PURPLE}``/``{RESET}``/etc. format tokens from a
    ``xcontext_main`` text dump so substring asserts can match the
    user-visible content directly.
    """
    return _COLOR_TOKENS_RE.sub("", text)


def _run_xcontext_main_with_resolve(xession, resolve_map):
    """Run ``xcontext_main`` with a stubbed ``_resolve_path`` that
    returns a custom ``resolved`` value for selected inputs, and return
    the rendered output with color tokens stripped.

    ``resolve_map`` is a dict mapping the input value (string or list,
    lists must be passed as tuples for hashability) to the resolved
    value the stub should report. Inputs absent from the map pass
    through unchanged (original == resolved).
    """
    buf = io.StringIO()
    fake_completed = subprocess.CompletedProcess(
        args=["python", "--version"],
        returncode=0,
        stdout="Python 3.13.3\n",
        stderr="",
    )
    xession.aliases["xpip"] = ["/fake/python", "-m", "pip"]

    def fake_resolve(value, resolve):
        key = tuple(value) if isinstance(value, list) else value
        target = resolve_map.get(key, value)
        return value, target, False

    with (
        mock.patch.object(xcontext.subprocess, "run", return_value=fake_completed),
        mock.patch.object(xcontext, "locate_executable", return_value="/fake/bin"),
        mock.patch.object(xcontext, "_resolve_path", side_effect=fake_resolve),
        mock.patch("xonsh.main.get_current_xonsh", return_value="/fake/xonsh"),
        mock.patch.object(
            xcontext,
            "print_color",
            side_effect=lambda s, file=None: print(s, file=file),
        ),
    ):
        xcontext.xcontext_main(_stdout=buf)
    return _strip_color_tokens(buf.getvalue())


def test_text_no_resolved_row_when_identical(xession):
    """When the resolved path is identical to the input, no second
    ``name resolved:`` row appears — it would just duplicate the line.
    """
    xession.env.pop("CONDA_DEFAULT_ENV", None)
    xession.env.pop("VIRTUAL_ENV", None)
    out = _run_xcontext_main_with_resolve(xession, resolve_map={})
    # No row in the output starts with "xxonsh resolved" / etc.
    assert "xxonsh resolved" not in out
    assert "xpython resolved" not in out
    assert "xpip resolved" not in out
    assert "xonsh resolved" not in out
    assert "python resolved" not in out
    assert "pip resolved" not in out


def test_text_resolved_row_emitted_when_xxonsh_differs(xession):
    """When the resolved xxonsh path differs from the input, a
    secondary ``xxonsh resolved:`` row appears with the resolved path.
    """
    xession.env.pop("CONDA_DEFAULT_ENV", None)
    xession.env.pop("VIRTUAL_ENV", None)
    out = _run_xcontext_main_with_resolve(
        xession, resolve_map={"/fake/xonsh": "/real/xonsh"}
    )
    # Original row carries the input path; resolved row carries the
    # symlink target.
    assert "xxonsh: /fake/xonsh" in out
    assert "xxonsh resolved: /real/xonsh" in out
    # The other families weren't remapped, so their resolved rows are
    # suppressed.
    assert "xpython resolved" not in out
    assert "xpip resolved" not in out


def test_text_resolved_row_emitted_for_xpip_list(xession):
    """A list-valued xpip whose head was symlink-resolved emits a
    secondary row with the joined resolved list.
    """
    xession.env.pop("CONDA_DEFAULT_ENV", None)
    xession.env.pop("VIRTUAL_ENV", None)
    out = _run_xcontext_main_with_resolve(
        xession,
        resolve_map={
            ("/fake/python", "-m", "pip"): ["/real/python", "-m", "pip"],
        },
    )
    assert "xpip: /fake/python -m pip" in out
    assert "xpip resolved: /real/python -m pip" in out


def test_text_resolved_row_repeats_version(xession):
    """The ``# Python X.Y.Z`` annotation is shown on BOTH the input row
    and the resolved row — the version describes the binary, not the
    spelling of the path.
    """
    xession.env.pop("CONDA_DEFAULT_ENV", None)
    xession.env.pop("VIRTUAL_ENV", None)
    out = _run_xcontext_main_with_resolve(
        xession, resolve_map={sys.executable: "/real/python3"}
    )
    # The ``xpython:`` row uses sys.executable, and the resolved row
    # carries our remap. Both should carry the version comment.
    version_lines = [ln for ln in out.splitlines() if "Python 3.13.3" in ln]
    # xpython input + xpython resolved + commands.python input + commands.python resolved
    # commands.python wasn't remapped (resolve_map keyed by sys.executable
    # only matches the session getter), so we expect at least 2 — the
    # session pair.
    assert len(version_lines) >= 2
    # Both session lines (xpython: ... # Python 3.13.3) and the
    # resolved variant carry the trailing comment.
    assert any(ln.lstrip().startswith("xpython:") for ln in version_lines)
    assert any(ln.lstrip().startswith("xpython resolved:") for ln in version_lines)


def test_text_no_resolved_row_when_path_missing(xession):
    """A missing entry (xpip with no alias) renders ``not found`` once;
    no spurious ``name resolved:`` row is emitted.
    """
    xession.env.pop("CONDA_DEFAULT_ENV", None)
    xession.env.pop("VIRTUAL_ENV", None)
    xession.aliases.pop("xpip", None)
    buf = io.StringIO()
    fake_completed = subprocess.CompletedProcess(
        args=["python", "--version"],
        returncode=0,
        stdout="Python 3.13.3\n",
        stderr="",
    )
    with (
        mock.patch.object(xcontext.subprocess, "run", return_value=fake_completed),
        mock.patch.object(xcontext, "locate_executable", return_value="/fake/bin"),
        mock.patch.object(
            xcontext, "_resolve_path", side_effect=lambda v, r: (v, v, False)
        ),
        mock.patch("xonsh.main.get_current_xonsh", return_value="/fake/xonsh"),
        mock.patch.object(
            xcontext,
            "print_color",
            side_effect=lambda s, file=None: print(s, file=file),
        ),
    ):
        xcontext.xcontext_main(_stdout=buf)
    out = _strip_color_tokens(buf.getvalue())
    assert "xpip: not found" in out
    assert "xpip resolved" not in out


def test_resolve_path_list_head_uses_pathext_probe(tmp_path, xession):
    """List-valued aliases (``xpip = [python, -m, pip]``) have only
    their head element probed — trailing args are passed through
    unchanged on both the original and the resolved side.
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
    original, resolved, bad = xcontext._resolve_path([bare, "-m", "pip"], resolve=True)
    assert original == [bare, "-m", "pip"]
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
            xcontext, "_resolve_path", side_effect=lambda v, r: (v, v, False)
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
    """``session`` carries each entry under its base key; ``xpip`` joins
    its list with spaces — same flat string the colored output shows
    for the ``xpip:`` row. With the stubbed ``_resolve_path``, original
    equals resolved, so no ``_resolved`` siblings appear.
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
    pytest/uv) so consumers don't have to special-case missing base
    keys. ``_resolved`` siblings are absent when the value matches —
    see :func:`test_json_resolved_keys_carry_distinct_values` for the
    differing case.
    """
    xession.env.pop("CONDA_DEFAULT_ENV", None)
    xession.env.pop("VIRTUAL_ENV", None)
    report, _ = _run_xcontext_json(xession)
    bases = {"xonsh", "python", "pip", "pytest", "uv"}
    assert set(report["commands"]) == bases
    for cmd in bases:
        assert report["commands"][cmd] == f"/fake/{cmd}"


def test_json_commands_null_when_not_on_path(xession):
    """A name absent from ``$PATH`` shows up as JSON ``null`` for its
    base key. The ``_resolved`` sibling is omitted (no resolution to
    add) — there's no key at all, not a ``null`` placeholder.
    """
    xession.env.pop("CONDA_DEFAULT_ENV", None)
    xession.env.pop("VIRTUAL_ENV", None)
    report, _ = _run_xcontext_json(xession, locate={"pytest": None, "uv": None})
    assert report["commands"]["pytest"] is None
    assert report["commands"]["uv"] is None
    assert report["commands"]["xonsh"] == "/fake/xonsh"
    # No ``_resolved`` siblings — stubbed ``_resolve_path`` returns
    # ``original == resolved`` for every value, including the ``None``s.
    assert "pytest_resolved" not in report["commands"]
    assert "uv_resolved" not in report["commands"]
    assert "xonsh_resolved" not in report["commands"]


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


def test_json_resolved_keys_carry_distinct_values(xession):
    """When resolution rewrites a path, the ``_resolved`` JSON key
    carries the new value while the base key keeps the input. Names
    that weren't rewritten ship without a ``_resolved`` sibling.
    """
    xession.env.pop("CONDA_DEFAULT_ENV", None)
    xession.env.pop("VIRTUAL_ENV", None)
    buf = io.StringIO()
    xession.aliases["xpip"] = ["/fake/python", "-m", "pip"]
    locate_map = {
        "xonsh": "/fake/xonsh",
        "python": "/fake/python",
        "pip": "/fake/pip",
        "pytest": "/fake/pytest",
        "uv": "/fake/uv",
    }
    rewrite = {
        "/fake/xonsh": "/real/xonsh",
        "/fake/python": "/real/python",
        ("/fake/python", "-m", "pip"): ["/real/python", "-m", "pip"],
    }

    def fake_resolve(value, resolve):
        key = tuple(value) if isinstance(value, list) else value
        return value, rewrite.get(key, value), False

    with (
        mock.patch.object(
            xcontext, "locate_executable", side_effect=lambda c: locate_map.get(c)
        ),
        mock.patch.object(xcontext, "_resolve_path", side_effect=fake_resolve),
        mock.patch("xonsh.main.get_current_xonsh", return_value="/fake/xonsh"),
    ):
        rc = xcontext.xcontext_main(as_json=True, _stdout=buf)
    assert rc == 0
    report = json.loads(buf.getvalue())
    # session: input vs resolved diverge for xxonsh and xpip; xpython
    # (sys.executable) is untouched by the rewrite map → no
    # xpython_resolved key.
    assert report["session"]["xxonsh"] == "/fake/xonsh"
    assert report["session"]["xxonsh_resolved"] == "/real/xonsh"
    assert report["session"]["xpip"] == "/fake/python -m pip"
    assert report["session"]["xpip_resolved"] == "/real/python -m pip"
    assert "xpython_resolved" not in report["session"]
    # commands: xonsh and python diverge; pip/pytest/uv aren't in the
    # rewrite map → no ``_resolved`` siblings.
    assert report["commands"]["xonsh"] == "/fake/xonsh"
    assert report["commands"]["xonsh_resolved"] == "/real/xonsh"
    assert report["commands"]["python"] == "/fake/python"
    assert report["commands"]["python_resolved"] == "/real/python"
    assert report["commands"]["pip"] == "/fake/pip"
    assert "pip_resolved" not in report["commands"]
    assert "pytest_resolved" not in report["commands"]
    assert "uv_resolved" not in report["commands"]


def test_json_no_resolve_flag_skips_resolved_keys(xession):
    """``xcontext -n --json`` (no_resolve=True) suppresses every
    ``_resolved`` sibling because the resolver leaves paths verbatim —
    matches the colored output's behavior under ``--no-resolve``.
    """
    xession.env.pop("CONDA_DEFAULT_ENV", None)
    xession.env.pop("VIRTUAL_ENV", None)
    xession.aliases["xpip"] = ["/fake/python", "-m", "pip"]
    buf = io.StringIO()
    locate_map = {
        cmd: f"/fake/{cmd}" for cmd in ("xonsh", "python", "pip", "pytest", "uv")
    }
    with (
        mock.patch.object(
            xcontext, "locate_executable", side_effect=lambda c: locate_map.get(c)
        ),
        # Pass the value through unchanged on both sides — the real
        # ``_resolve_path`` does the same in ``-n`` mode when nothing
        # needs the PATHEXT fallback.
        mock.patch.object(
            xcontext, "_resolve_path", side_effect=lambda v, r: (v, v, False)
        ),
        mock.patch("xonsh.main.get_current_xonsh", return_value="/fake/xonsh"),
    ):
        rc = xcontext.xcontext_main(no_resolve=True, as_json=True, _stdout=buf)
    assert rc == 0
    report = json.loads(buf.getvalue())
    for section in ("session", "commands"):
        assert not any(k.endswith("_resolved") for k in report[section])


# ---------------------------------------------------------------------------
# Resolved dataclass — display rendering
# ---------------------------------------------------------------------------


def test_resolved_display_string_path():
    """A plain string path is returned as-is."""
    r = xcontext.Resolved(path="/usr/bin/xonsh")
    assert r.display == "/usr/bin/xonsh"


def test_resolved_display_list_path_joined_with_spaces():
    """A list path (xpip alias) is space-joined for the colored row and
    the JSON ``session.xpip`` field — same shape both consumers expect.
    """
    r = xcontext.Resolved(path=["/usr/bin/python", "-m", "pip"])
    assert r.display == "/usr/bin/python -m pip"


def test_resolved_display_none_path():
    """``path=None`` (not found / no such alias) renders as ``None`` so
    callers can distinguish "missing" from "empty string"."""
    assert xcontext.Resolved(path=None).display is None
    assert xcontext.Resolved().display is None


def test_resolved_display_empty_string():
    """Falsy ``path`` (empty string) also renders as ``None`` — same
    "missing" signal as ``path=None``."""
    assert xcontext.Resolved(path="").display is None


def test_resolved_display_list_with_non_string_passthrough():
    """A list whose elements aren't all strings can't be space-joined —
    fall back to ``str(path)`` rather than raising."""
    value = [object(), "-m", "pip"]
    assert xcontext.Resolved(path=value).display == str(value)


def test_resolved_defaults_are_safe():
    """Default ``Resolved()`` is a "nothing found" placeholder — bad is
    False, version is empty, path and resolved are None. Lets callers
    construct from optional fields without juggling sentinels.
    """
    r = xcontext.Resolved()
    assert r.path is None
    assert r.resolved is None
    assert r.bad is False
    assert r.version == ""


def test_resolved_resolved_display_string():
    """``resolved_display`` renders the ``resolved`` field the same way
    ``display`` renders ``path`` — a plain string passes through.
    """
    r = xcontext.Resolved(path="/bin/python", resolved="/usr/bin/python3.13")
    assert r.resolved_display == "/usr/bin/python3.13"


def test_resolved_resolved_display_list_joined_with_spaces():
    """A list ``resolved`` (xpip alias) joins with spaces the same way
    ``display`` does for ``path``.
    """
    r = xcontext.Resolved(
        path=["/bin/python", "-m", "pip"],
        resolved=["/usr/bin/python3.13", "-m", "pip"],
    )
    assert r.resolved_display == "/usr/bin/python3.13 -m pip"


def test_resolved_resolved_display_none():
    """``resolved=None`` renders as ``None`` so callers can detect
    "no resolution available" without re-checking the field.
    """
    assert xcontext.Resolved(path="/x").resolved_display is None
    assert xcontext.Resolved().resolved_display is None


def test_resolved_differs_false_when_equal():
    """When the input and the resolved path are the same string, the
    colored renderer must collapse to a single ``name:`` row.
    """
    r = xcontext.Resolved(path="/bin/python", resolved="/bin/python")
    assert r.differs is False


def test_resolved_differs_true_when_distinct():
    """A symlink resolution produces distinct input/resolved values —
    the colored renderer emits the secondary ``name resolved:`` row.
    """
    r = xcontext.Resolved(path="/bin/python", resolved="/usr/bin/python3.13")
    assert r.differs is True


def test_resolved_differs_false_when_resolved_none():
    """``resolved=None`` (the "not found / placeholder" shape) must not
    drive the secondary row — there's nothing to render.
    """
    assert xcontext.Resolved(path="/x").differs is False
    assert xcontext.Resolved().differs is False


def test_resolved_differs_for_list_compares_elementwise():
    """Two list values with different head executables differ; equal
    lists do not. Drives the ``xpip resolved:`` row.
    """
    r_same = xcontext.Resolved(
        path=["/bin/python", "-m", "pip"],
        resolved=["/bin/python", "-m", "pip"],
    )
    r_diff = xcontext.Resolved(
        path=["/bin/python", "-m", "pip"],
        resolved=["/usr/bin/python3.13", "-m", "pip"],
    )
    assert r_same.differs is False
    assert r_diff.differs is True


# ---------------------------------------------------------------------------
# XContext — session getters
# ---------------------------------------------------------------------------


def test_xcontext_get_session_xxonsh_returns_resolved(xession):
    """``get_session_xxonsh`` returns the resolved running interpreter
    wrapped in a :class:`Resolved`. Stub ``_resolve_path`` so the test
    is independent of what's actually on disk.
    """
    with (
        mock.patch.object(
            xcontext, "_resolve_path", side_effect=lambda v, r: (v, v, False)
        ),
        mock.patch("xonsh.main.get_current_xonsh", return_value="/fake/xonsh"),
    ):
        r = xcontext.XContext().get_session_xxonsh()
    assert isinstance(r, xcontext.Resolved)
    assert r.path == "/fake/xonsh"
    assert r.bad is False


def test_xcontext_get_session_xxonsh_passes_resolve_flag(xession):
    """``XContext(resolve=False)`` must propagate that to ``_resolve_path``
    so ``--no-resolve`` actually skips symlink chasing.
    """
    seen = []

    def fake(value, resolve):
        seen.append(resolve)
        return value, value, False

    with (
        mock.patch.object(xcontext, "_resolve_path", side_effect=fake),
        mock.patch("xonsh.main.get_current_xonsh", return_value="/fake/xonsh"),
    ):
        xcontext.XContext(resolve=False).get_session_xxonsh()
    assert seen == [False]


def test_xcontext_get_session_xxonsh_caches_when_enabled(xession):
    """With ``cache=True`` two calls to ``get_session_xxonsh`` must hit
    the per-instance cache and only resolve once. Without the cache,
    every property read in ``xcontext_main`` would re-import
    ``xonsh.main`` (heavy) and re-resolve the path.
    """
    calls = mock.MagicMock(return_value="/fake/xonsh")
    with (
        mock.patch.object(
            xcontext, "_resolve_path", side_effect=lambda v, r: (v, v, False)
        ),
        mock.patch("xonsh.main.get_current_xonsh", side_effect=calls),
    ):
        xc = xcontext.XContext(cache=True)
        first = xc.get_session_xxonsh()
        second = xc.get_session_xxonsh()
    assert first is second  # same Resolved instance, not a fresh one
    assert calls.call_count == 1


def test_xcontext_default_does_not_cache(xession):
    """Default ``XContext()`` has ``cache=False`` so a long-lived holder
    (e.g. an xontrib that stashes the instance) sees fresh ``$PATH`` /
    alias state on every read instead of a stale snapshot.
    """
    calls = mock.MagicMock(return_value="/fake/xonsh")
    with (
        mock.patch.object(
            xcontext, "_resolve_path", side_effect=lambda v, r: (v, v, False)
        ),
        mock.patch("xonsh.main.get_current_xonsh", side_effect=calls),
    ):
        xc = xcontext.XContext()
        first = xc.get_session_xxonsh()
        second = xc.get_session_xxonsh()
    # Each call re-runs the underlying probe → distinct Resolved
    # objects (equal-valued, but freshly built).
    assert first is not second
    assert calls.call_count == 2


def test_xcontext_get_session_xpython_records_version(xession):
    """``get_session_xpython`` runs ``--version`` once and stores the
    trimmed string on the returned :class:`Resolved`.
    """
    completed = subprocess.CompletedProcess(
        args=["python", "--version"],
        returncode=0,
        stdout="Python 3.13.3\n",
        stderr="",
    )
    with (
        mock.patch.object(
            xcontext, "_resolve_path", side_effect=lambda v, r: (v, v, False)
        ),
        mock.patch.object(xcontext.subprocess, "run", return_value=completed) as run,
    ):
        r = xcontext.XContext().get_session_xpython()
    assert r.version == "Python 3.13.3"
    assert r.bad is False
    assert run.call_count == 1


def test_xcontext_get_session_xpython_marks_bad_on_spawn_error(xession):
    """A spawn error (Windows Store ``python.exe`` alias case) must
    propagate to ``Resolved.bad`` even when path resolution itself
    succeeded.
    """
    with (
        mock.patch.object(
            xcontext, "_resolve_path", side_effect=lambda v, r: (v, v, False)
        ),
        mock.patch.object(
            xcontext.subprocess,
            "run",
            side_effect=OSError(1920, "The file cannot be accessed by the system"),
        ),
    ):
        r = xcontext.XContext().get_session_xpython()
    assert r.bad is True
    assert r.version == ""


def test_xcontext_get_session_xpython_caches_subprocess_when_enabled(xession):
    """With ``cache=True`` the version probe is only allowed to run once
    per instance — every extra spawn would slow down ``xcontext`` and
    (worse) could produce inconsistent output between rows of the same
    report.
    """
    completed = subprocess.CompletedProcess(
        args=["python", "--version"], returncode=0, stdout="Python 3.13.3\n", stderr=""
    )
    with (
        mock.patch.object(
            xcontext, "_resolve_path", side_effect=lambda v, r: (v, v, False)
        ),
        mock.patch.object(xcontext.subprocess, "run", return_value=completed) as run,
    ):
        xc = xcontext.XContext(cache=True)
        xc.get_session_xpython()
        xc.get_session_xpython()
    assert run.call_count == 1


def test_xcontext_default_reruns_subprocess(xession):
    """With cache off (the default), each call re-spawns the probe.
    Documents the contract: long-lived holders pay the spawn cost on
    every read but always see current state.
    """
    completed = subprocess.CompletedProcess(
        args=["python", "--version"], returncode=0, stdout="Python 3.13.3\n", stderr=""
    )
    with (
        mock.patch.object(
            xcontext, "_resolve_path", side_effect=lambda v, r: (v, v, False)
        ),
        mock.patch.object(xcontext.subprocess, "run", return_value=completed) as run,
    ):
        xc = xcontext.XContext()
        xc.get_session_xpython()
        xc.get_session_xpython()
    assert run.call_count == 2


def test_xcontext_get_session_xpip_returns_alias(xession):
    """``get_session_xpip`` reads ``XSH.aliases['xpip']`` (typically a
    ``[python, -m, pip]`` list) and the :attr:`Resolved.display` joins
    it with spaces — the same shape the JSON ``session.xpip`` field
    serializes.
    """
    xession.aliases["xpip"] = ["/fake/python", "-m", "pip"]
    with mock.patch.object(
        xcontext, "_resolve_path", side_effect=lambda v, r: (v, v, False)
    ):
        r = xcontext.XContext().get_session_xpip()
    assert r.path == ["/fake/python", "-m", "pip"]
    assert r.resolved == ["/fake/python", "-m", "pip"]
    assert r.display == "/fake/python -m pip"
    assert r.bad is False


def test_xcontext_get_session_xpip_missing_alias(xession):
    """If ``xpip`` isn't aliased, the getter returns a "not found"
    Resolved (path is None, display is None) — the colored renderer
    falls back to the literal string ``not found``.
    """
    xession.aliases.pop("xpip", None)
    with mock.patch.object(
        xcontext, "_resolve_path", side_effect=lambda v, r: (v, v, False)
    ):
        r = xcontext.XContext().get_session_xpip()
    assert r.path is None
    assert r.resolved is None
    assert r.display is None


# ---------------------------------------------------------------------------
# XContext — commands getters
# ---------------------------------------------------------------------------


def test_xcontext_get_commands_xonsh_uses_locate_executable(xession):
    """The ``xonsh`` row in the commands section is whatever
    :func:`locate_executable` returns for ``xonsh``."""
    with (
        mock.patch.object(xcontext, "locate_executable", return_value="/path/xonsh"),
        mock.patch.object(
            xcontext, "_resolve_path", side_effect=lambda v, r: (v, v, False)
        ),
    ):
        r = xcontext.XContext().get_commands_xonsh()
    assert r.path == "/path/xonsh"
    assert r.bad is False


def test_xcontext_get_commands_python_records_version(xession):
    """The ``python`` commands row runs the same ``--version`` probe so
    the row can show ``# Python X.Y.Z`` and flag the spawn-broken case.
    """
    completed = subprocess.CompletedProcess(
        args=["python", "--version"],
        returncode=0,
        stdout="Python 3.13.3\n",
        stderr="",
    )
    with (
        mock.patch.object(xcontext, "locate_executable", return_value="/path/python"),
        mock.patch.object(
            xcontext, "_resolve_path", side_effect=lambda v, r: (v, v, False)
        ),
        mock.patch.object(xcontext.subprocess, "run", return_value=completed),
    ):
        r = xcontext.XContext().get_commands_python()
    assert r.path == "/path/python"
    assert r.version == "Python 3.13.3"
    assert r.bad is False


def test_xcontext_get_commands_python_skips_probe_when_missing(xession):
    """If python isn't on ``$PATH``, no version probe is attempted —
    spawning ``None --version`` would raise."""
    with (
        mock.patch.object(xcontext, "locate_executable", return_value=None),
        mock.patch.object(
            xcontext, "_resolve_path", side_effect=lambda v, r: (v, v, False)
        ),
        mock.patch.object(xcontext.subprocess, "run") as run,
    ):
        r = xcontext.XContext().get_commands_python()
    assert r.path is None
    assert r.version == ""
    assert run.call_count == 0


def test_xcontext_get_commands_python_marks_bad_on_spawn_error(xession):
    """Same Windows Store alias case as the session row, but for the
    PATH-resolved python."""
    with (
        mock.patch.object(xcontext, "locate_executable", return_value="/store/python"),
        mock.patch.object(
            xcontext, "_resolve_path", side_effect=lambda v, r: (v, v, False)
        ),
        mock.patch.object(
            xcontext.subprocess, "run", side_effect=OSError(1920, "WinError 1920")
        ),
    ):
        r = xcontext.XContext().get_commands_python()
    assert r.bad is True


def test_xcontext_get_commands_pip_pytest_uv(xession):
    """The remaining commands rows are plain PATH lookups — no version
    probe, just a Resolved wrapping whatever ``locate_executable`` finds.
    Parameterized via dict to keep the assertions tight.
    """
    locate_map = {"pip": "/path/pip", "pytest": "/path/pytest", "uv": "/path/uv"}
    with (
        mock.patch.object(
            xcontext, "locate_executable", side_effect=lambda c: locate_map.get(c)
        ),
        mock.patch.object(
            xcontext, "_resolve_path", side_effect=lambda v, r: (v, v, False)
        ),
    ):
        xc = xcontext.XContext()
        assert xc.get_commands_pip().path == "/path/pip"
        assert xc.get_commands_pytest().path == "/path/pytest"
        assert xc.get_commands_uv().path == "/path/uv"


def test_xcontext_get_commands_missing_returns_none(xession):
    """A name not on ``$PATH`` produces ``Resolved(path=None)`` — the
    JSON output relies on this to emit ``null`` for missing entries.
    """
    with (
        mock.patch.object(xcontext, "locate_executable", return_value=None),
        mock.patch.object(
            xcontext, "_resolve_path", side_effect=lambda v, r: (v, v, False)
        ),
    ):
        r = xcontext.XContext().get_commands_pytest()
    assert r.path is None


def test_xcontext_get_commands_caches_when_enabled(xession):
    """With ``cache=True`` each commands getter is cached — repeated
    reads in ``xcontext_main`` (color check + row print) only hit
    ``locate_executable`` once.
    """
    locate = mock.MagicMock(return_value="/path/xonsh")
    with (
        mock.patch.object(xcontext, "locate_executable", side_effect=locate),
        mock.patch.object(
            xcontext, "_resolve_path", side_effect=lambda v, r: (v, v, False)
        ),
    ):
        xc = xcontext.XContext(cache=True)
        first = xc.get_commands_xonsh()
        second = xc.get_commands_xonsh()
    assert first is second
    assert locate.call_count == 1


# ---------------------------------------------------------------------------
# XContext — env getters
# ---------------------------------------------------------------------------


def test_xcontext_env_getters_return_set_values(xession):
    xession.env["CONDA_DEFAULT_ENV"] = "myenv"
    xession.env["VIRTUAL_ENV"] = "/tmp/venv"
    xc = xcontext.XContext()
    assert xc.get_env_conda_default_env() == "myenv"
    assert xc.get_env_virtual_env() == "/tmp/venv"


def test_xcontext_env_getters_return_none_when_unset(xession):
    xession.env.pop("CONDA_DEFAULT_ENV", None)
    xession.env.pop("VIRTUAL_ENV", None)
    xc = xcontext.XContext()
    assert xc.get_env_conda_default_env() is None
    assert xc.get_env_virtual_env() is None
