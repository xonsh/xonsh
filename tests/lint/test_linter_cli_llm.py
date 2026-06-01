"""Tests for ``xonsh lint`` and the lint rules.

The linter runs over the transformed xonsh AST (no execution) and ships four
MVP rules: XSH001 (env-var typo), XSH002 (bad env-var literal), XSH003
(deprecated env var), XSH101 (unused import).
"""

from __future__ import annotations

import io
import sys

import pytest

from xonsh.linter import cli as lcli


def codes(src):
    return [f.code for f in lcli.lint_source(src)]


def _run(argv, capsys, monkeypatch, stdin_text=None):
    if stdin_text is not None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(stdin_text))
    rc = lcli.main(argv)
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


# ---------------------------------------------------------------------
# XSH001 — env-var typo
# ---------------------------------------------------------------------


def test_xsh001_typo_read():
    fs = lcli.lint_source("x = $XONSH_COLOR_STYL")
    assert [f.code for f in fs] == ["XSH001"]
    assert "XONSH_COLOR_STYLE" in fs[0].message


def test_xsh001_typo_write():
    fs = lcli.lint_source('$XONSH_HISTROY_BACKEND = "json"')
    assert [f.code for f in fs] == ["XSH001"]
    assert "XONSH_HISTORY_BACKEND" in fs[0].message


def test_xsh001_custom_var_silent():
    # A genuinely custom env var (no close match) must not be flagged.
    assert codes('$DATABASE_URL = "postgres://x"') == []


# ---------------------------------------------------------------------
# XSH002 — bad env-var literal value
# ---------------------------------------------------------------------


def test_xsh002_quoted_bool():
    fs = lcli.lint_source('$XONSH_STORE_STDOUT = "yes"')
    assert [f.code for f in fs] == ["XSH002"]
    assert "XONSH_STORE_STDOUT" in fs[0].message


def test_xsh002_valid_value_silent():
    assert codes("$XONSH_STORE_STDOUT = True") == []


def test_xsh002_string_var_silent():
    # A string value for a string-typed var is fine.
    assert "XSH002" not in codes('$TITLE = "{current_job:{} | }{cwd}"')


# ---------------------------------------------------------------------
# XSH003 — deprecated env var
# ---------------------------------------------------------------------


def test_xsh003_deprecated_write():
    fs = lcli.lint_source("$RAISE_SUBPROC_ERROR = True")
    assert [f.code for f in fs] == ["XSH003"]


def test_xsh003_deprecated_read():
    assert codes("x = $AUTO_SUGGEST") == ["XSH003"]


# ---------------------------------------------------------------------
# XSH101 — unused import
# ---------------------------------------------------------------------


def test_xsh101_unused_import():
    fs = lcli.lint_source("import os\nx = 1")
    assert [f.code for f in fs] == ["XSH101"]
    assert "'os'" in fs[0].message


def test_xsh101_used_in_pyeval_silent():
    assert codes("import json\necho @(json.dumps(1))") == []


def test_xsh101_from_import_unused():
    fs = lcli.lint_source("from os import path\nx = 1")
    assert [f.code for f in fs] == ["XSH101"]
    assert "os.path" in fs[0].message


def test_xsh101_future_import_silent():
    assert codes("from __future__ import annotations\nx = 1") == []


def test_xsh101_dunder_all_counts_as_used():
    assert codes('import os\n__all__ = ["os"]') == []


def test_xsh101_star_import_silent():
    assert codes("from os import *\nx = 1") == []


# ---------------------------------------------------------------------
# Engine behaviour
# ---------------------------------------------------------------------


def test_clean_source_no_findings():
    assert codes("x = 1\nls -l | grep foo\necho @(x)") == []


def test_comment_only_no_findings():
    assert codes("# just a note") == []


def test_findings_sorted_by_position():
    src = "import os\nimport sys\n"  # two unused imports
    fs = lcli.lint_source(src)
    assert [f.line for f in fs] == [1, 2]
    assert all(f.code == "XSH101" for f in fs)


def test_syntax_error_propagates():
    with pytest.raises(SyntaxError):
        lcli.lint_source("x = (1 +")


def test_ignore_filters_codes():
    src = "import os\nx = 1"
    assert lcli.lint_source(src, ignore={"XSH101"}) == []


# ---------------------------------------------------------------------
# CLI: xonsh lint FILE...
# ---------------------------------------------------------------------


def test_cli_clean_file(tmp_path, capsys, monkeypatch):
    f = tmp_path / "a.xsh"
    f.write_text("x = 1\n")
    rc, out, err = _run([str(f)], capsys, monkeypatch)
    assert rc == lcli.EXIT_OK
    assert f"{f}: clean" in err


def test_cli_file_with_findings(tmp_path, capsys, monkeypatch):
    f = tmp_path / "bad.xsh"
    f.write_text("import os\n")
    rc, out, err = _run([str(f)], capsys, monkeypatch)
    assert rc == lcli.EXIT_LINT
    assert "XSH101" in err
    assert str(f) in err


def test_cli_quiet_suppresses_clean(tmp_path, capsys, monkeypatch):
    f = tmp_path / "a.xsh"
    f.write_text("x = 1\n")
    rc, out, err = _run([str(f), "-q"], capsys, monkeypatch)
    assert rc == lcli.EXIT_OK
    assert err == ""


def test_cli_ignore_flag(tmp_path, capsys, monkeypatch):
    f = tmp_path / "imp.xsh"
    f.write_text("import os\n")
    rc, out, err = _run([str(f), "--ignore", "XSH101"], capsys, monkeypatch)
    assert rc == lcli.EXIT_OK


def test_cli_missing_file(tmp_path, capsys, monkeypatch):
    rc, out, err = _run([str(tmp_path / "nope.xsh")], capsys, monkeypatch)
    assert rc == lcli.EXIT_ERROR
    assert "error" in err


def test_cli_syntax_error_file(tmp_path, capsys, monkeypatch):
    f = tmp_path / "broken.xsh"
    f.write_text("x = (1 +\n")
    rc, out, err = _run([str(f)], capsys, monkeypatch)
    assert rc == lcli.EXIT_ERROR
    assert str(f) in err


def test_cli_stdin(capsys, monkeypatch):
    rc, out, err = _run(["-"], capsys, monkeypatch, stdin_text="import os\n")
    assert rc == lcli.EXIT_LINT
    assert "<stdin>" in err and "XSH101" in err


# ---------------------------------------------------------------------
# Wiring: main() dispatch
# ---------------------------------------------------------------------


def test_main_dispatches_lint(tmp_path):
    import xonsh.main

    f = tmp_path / "a.xsh"
    f.write_text("x = 1\n")
    with pytest.raises(SystemExit) as ei:
        xonsh.main.main(["lint", str(f), "-q"])
    assert ei.value.code == lcli.EXIT_OK


def test_main_dispatches_lint_findings(tmp_path):
    import xonsh.main

    f = tmp_path / "imp.xsh"
    f.write_text("import os\n")
    with pytest.raises(SystemExit) as ei:
        xonsh.main.main(["lint", str(f)])
    assert ei.value.code == lcli.EXIT_LINT
