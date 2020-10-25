#!/usr/bin/env xonsh
"""Generates workflow files for each build matrix element. This is done
so that we can restart indivual workflow elements without having to restart
them all. Rerun this script to regenerate.
"""
from itertools import product
import os


OS_NAMES = ["linux", "macos", "windows"]
OS_IMAGES = {
    "linux": "ubuntu-latest",
    "macos": "macOS-latest",
    "windows": "windows-latest",
}
PYTHON_VERSIONS = ["3.6", "3.7", "3.8", "3.9"]

CURR_DIR = os.path.dirname(__file__)
template_path = os.path.join(CURR_DIR, "pytest.tmpl")

template = $(cat @(template_path))
for os_name, python_version in product(OS_NAMES, PYTHON_VERSIONS):
    s = template.replace("OS_NAME", os_name)
    s = s.replace("OS_IMAGE", OS_IMAGES[os_name])
    s = s.replace("PYTHON_VERSION", python_version)
    # Allow Python 3.9 to fail.
    if python_version in ["3.9"]:
        s = "\n".join((s, "        continue-on-error: true\n"))
    fname = os.path.join(CURR_DIR, f"pytest-{os_name}-{python_version}.yml")
    ![echo @(s) > @(fname)]
