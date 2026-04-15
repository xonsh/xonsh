"""Hatch custom build hook for xonsh.

Generate PLY parser tables and set Python-version-specific wheel tags.
"""

import os
import sys

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

TABLES = [
    "xonsh/parser_table.py",
    "xonsh/completion_parser_table.py",
]


def _python_tag():
    """Return the Python version tag, e.g. ``py313``."""
    return f"py{sys.version_info.major}{sys.version_info.minor}"


def _clean_tables(root):
    """Remove generated parser table files."""
    for table in TABLES:
        path = os.path.join(root, table)
        if os.path.isfile(path):
            os.remove(path)
            print(f"Removed {path}")


def _build_tables(root):
    """Generate PLY parser and completion parser tables."""
    print("Building lexer and parser tables.", file=sys.stderr)
    # XONSH_DEBUG=1 is required for parser table generation
    os.environ["XONSH_DEBUG"] = "1"
    sys.path.insert(0, root)
    try:
        from xonsh.parser import Parser
        from xonsh.parsers.completion_context import CompletionContextParser

        Parser(
            yacc_table="parser_table",
            outputdir=os.path.join(root, "xonsh"),
            yacc_debug=True,
        )
        CompletionContextParser(
            yacc_table="completion_parser_table",
            outputdir=os.path.join(root, "xonsh"),
            debug=True,
        )
    finally:
        sys.path.pop(0)


class CustomBuildHook(BuildHookInterface):
    """Custom build hook for xonsh parser tables and wheel tags."""

    PLUGIN_NAME = "custom"

    def initialize(self, version, build_data):
        """Generate parser tables and set wheel tag."""
        root = self.root

        _clean_tables(root)
        _build_tables(root)

        # Force-include the generated table files (they are gitignored)
        for table in TABLES:
            src = os.path.join(root, table)
            if os.path.isfile(src):
                build_data["force_include"][src] = table

        # Set Python-version-specific wheel tag
        if self.target_name == "wheel":
            build_data["tag"] = f"{_python_tag()}-none-any"

    def clean(self, versions):
        """Remove generated parser tables."""
        _clean_tables(self.root)
