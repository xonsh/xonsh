"""Regression tests for parser table generation in the build backend."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

# Mirrors ``build_tables()`` in setup.py. setup.py itself is not imported:
# it needs setuptools and wheel, which are build-time only requirements and
# may be missing from the environment the tests run in.
BUILD_TABLES = """
import os
import sys

sys.path.insert(0, os.getcwd())
from xonsh.parser import Parser
from xonsh.parsers.completion_context import CompletionContextParser

outputdir = os.path.join(os.getcwd(), "xonsh")
Parser(yacc_table="parser_table", outputdir=outputdir, yacc_debug=True)
CompletionContextParser(
    yacc_table="completion_parser_table", outputdir=outputdir, debug=True
)
"""


def test_parser_tables_reproducible_across_hash_seeds(tmp_path):
    root = Path(__file__).resolve().parents[1]
    tables = []
    for seed in ("1", "123"):
        build = tmp_path / seed
        build.mkdir()
        shutil.copytree(
            root / "xonsh",
            build / "xonsh",
            ignore=shutil.ignore_patterns("__pycache__", "*table.py"),
        )
        # Build under different hash seeds: no set iteration order may reach
        # the grammar, or PLY would number productions differently per build.
        proc = subprocess.run(
            [sys.executable, "-c", BUILD_TABLES],
            cwd=build,
            env=dict(os.environ, PYTHONHASHSEED=seed, XONSH_DEBUG="1"),
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stderr
        tables.append(
            {
                name: (build / "xonsh" / name).read_bytes()
                for name in (
                    "parser_table.py",
                    "completion_parser_table.py",
                )
            }
        )
    assert tables[0] == tables[1]
