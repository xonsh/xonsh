"""Regression coverage for reproducible documentation generation."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def test_documentation_omits_runtime_values(tmp_path):
    pytest.importorskip("sphinx")
    root = Path(__file__).resolve().parents[1]
    docs = tmp_path / "docs"
    docs.mkdir()
    shutil.copy2(root / "docs" / "conf.py", docs / "conf.py")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            r"""
import os
import runpy
import re
from html import unescape
from pathlib import Path
from sphinx.application import Sphinx
from xonsh.environ import Env, SystemSetting

conf = runpy.run_path('conf.py')
# Importing the documentation configuration must not replace the runtime PWD.
assert SystemSetting.PWD.default == os.getcwd()
group = conf['_gather_groups'](SystemSetting, Env())
for name in ('HOSTNAME', 'HOSTTYPE'):
    assert ' at 0x' not in group.vars[name].info['default']

# Render the affected attribute and CLI signatures through real autodoc. Limit
# extensions to those needed here so this regression test stays offline.
Path('index.rst').write_text(
    "API\n===\n\n"
    ".. autoattribute:: xonsh.environ.SystemSetting.PWD\n\n"
    ".. autofunction:: xonsh.completers.completer.remove_completer\n\n"
    ".. automethod:: xonsh.tracer.TracerType.toggle_color\n\n"
    ".. automethod:: xonsh.environ.Var.with_default\n"
)
with Path('conf.py').open('a') as stream:
    stream.write(
        "\nextensions = ['sphinx.ext.autodoc', 'sphinx.ext.duration']\n"
    )
    stream.write("html_theme = 'basic'\n")
    stream.write("master_doc = 'index'\n")
    stream.write("autosummary_generate = False\n")
    stream.write("html_additional_pages = {}\n")
    stream.write("html_static_path = []\n")
    stream.write("html_extra_path = []\n")
    stream.write("html_logo = None\n")
    stream.write("html_favicon = None\n")
    stream.write("exclude_patterns = ['output', 'doctrees']\n")
app = Sphinx('.', '.', 'output', 'doctrees', 'html', freshenv=True)
app.build(force_all=True)
html = Path('output/index.html').read_text()
assert 'SystemSetting.PWD' in html
assert 'remove_completer' in html
assert os.getcwd() not in html
assert ' at 0x' not in html

def signature(name):
    match = re.search(r'<dt[^>]*id="' + re.escape(name) + r'"[^>]*>(.*?)</dt>', html, re.S)
    assert match is not None, name
    return unescape(re.sub('<[^>]*>', '', match.group(1)))

# CLI metadata names its completers and converters instead of showing their
# process-specific repr.
assert 'Arg(completer=complete_completer_names)' in signature(
    'xonsh.completers.completer.remove_completer'
)
assert 'Arg(type=to_bool)' in signature('xonsh.tracer.TracerType.toggle_color')
# Classmethods must keep their signatures too.
assert 'default' in signature('xonsh.environ.Var.with_default')
# Rendering the signatures must leave the CLI built from them usable.
from xonsh.tracer import tracermain
try:
    tracermain(['color', '--help'])
except SystemExit:
    pass
assert not Path('output/sphinx-reading-durations.json').exists()

""",
        ],
        cwd=docs,
        env=dict(
            os.environ,
            PYTHONPATH=str(root) + os.pathsep + os.environ.get("PYTHONPATH", ""),
        ),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
