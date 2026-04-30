import os
import stat
import sys

# Ensure the source tree is on sys.path so that xonsh is imported from here,
# not from site-packages. This is needed for bare `pytest` and IDE runners.
_root = os.path.dirname(os.path.abspath(__file__))
if _root not in sys.path:
    sys.path.insert(0, _root)

import xonsh as _xonsh  # noqa: E402

_expected = os.path.abspath(os.path.join(_root, "xonsh", "__init__.py"))
_actual = os.path.abspath(_xonsh.__file__)
if _actual != _expected:
    raise RuntimeError(
        "\nXonsh package is installed. The `pytest` command will not work correctly and will use it instead of the "
        "source tree:\n"
        f" * Source tree: {_expected!r}\n"
        f" * Site-packages: {_actual!r}\n"
        f"Use `cd {_root!r} && python -m pytest` to ensure that xonsh is tested from the source tree rather than site-packages."
    )

# Render tests/bin/<name> from tests/bin/templates/<name> with a shebang that
# uses the current pytest interpreter. The interpreter that runs pytest is the
# one that should run the helper scripts, so a hardcoded ``#!/usr/bin/env
# python3`` or ``#!/usr/bin/env xonsh`` is wrong on systems where those names
# are missing (e.g. FreeBSD ports building against a single ``python3.11``,
# or any environment where the ``xonsh`` console_script isn't on $PATH).
#
# Plain Python scripts get ``#!<sys.executable>``. ``*.xsh`` scripts get a
# multi-arg shebang via ``env -S`` so they invoke ``<sys.executable> -m xonsh``,
# which works without relying on the ``xonsh`` launcher binary. ``env -S`` is
# supported on Linux (coreutils 8.30+, 2018), FreeBSD, and macOS 10.15+.
#
# Done at conftest module-load time so it fires for every pytest invocation,
# including ``pytest path/to/file.py::test_name``.
_templates_dir = os.path.join(_root, "tests", "bin", "templates")
if os.path.isdir(_templates_dir):
    _py_shebang = f"#!{sys.executable}\n"
    _xsh_shebang = f"#!/usr/bin/env -S {sys.executable} -m xonsh\n"
    for _name in os.listdir(_templates_dir):
        _src = os.path.join(_templates_dir, _name)
        if not os.path.isfile(_src):
            continue
        with open(_src, encoding="utf-8") as _f:
            _body = _f.read()
        _shebang = _xsh_shebang if _name.endswith(".xsh") else _py_shebang
        _dst = os.path.join(_root, "tests", "bin", _name)
        with open(_dst, "w", encoding="utf-8") as _f:
            _f.write(_shebang + _body)
        os.chmod(
            _dst,
            os.stat(_dst).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH,
        )

# Load the xonsh pytest plugin (provides xession fixture, etc.).
# With `python -m pytest` it's already loaded via the entry point;
# with bare `pytest` or IDE runners it needs to be loaded explicitly.
if "xonsh.pytest.plugin" not in sys.modules:
    pytest_plugins = ("xonsh.pytest.plugin",)
