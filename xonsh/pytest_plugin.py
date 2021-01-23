# -*- coding: utf-8 -*-
"""Pytest plugin for testing xsh files."""
import _pytest.pathlib

from xonsh.main import setup


class XshPytestPlugin:
    def __init__(self):
        setup()

    def pytest_collect_file(self, path, parent):
        if path.ext.lower() == ".xsh":
            if not parent.session.isinitpath(path):
                all_valid_test_file_patterns = parent.config.getini("python_files") + [
                    "__init__.py"
                ]
                if not any(
                    _pytest.pathlib.fnmatch_ex(pattern, path)
                    for pattern in all_valid_test_file_patterns
                ):
                    return None
            i_hook = parent.session.gethookproxy(path)
            return i_hook.pytest_pycollect_makemodule(
                fspath=path, path=path, parent=parent
            )
        return None


def pytest_addoption(parser):
    group = parser.getgroup("xonsh", "Collecting and running .xsh pytest files")
    group.addoption(
        "--xonsh",
        default=False,
        action="store_true",
        help="Enables collecting and running xonsh test files ending with .xsh",
    )


def pytest_configure(config):
    if config.option.xonsh:
        config.pluginmanager.register(XshPytestPlugin())
