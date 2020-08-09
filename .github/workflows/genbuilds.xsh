#!/usr/bin/env xonsh
"""Generates workflow files for each build matrix element. This is done
so that we can restart indivual workflow elements without having to restart
them all. Rerun this script to regenerate.
"""
from itertools import product


OS_NAMES = ["linux", "macos", "windows"]
OS_IMAGES = {
    "linux": "ubuntu-latest",
    "macos": "macOS-latest",
    "windows": "windows-latest",
}
PYTHON_VERSIONS = ["3.6", "3.7", "3.8"]

template = $(cat pytest.tmpl)
for os_name, python_version in product(OS_NAMES, PYTHON_VERSIONS):
    s = template.replace("OS_NAME", os_name)
    s = s.replace("OS_IMAGE", OS_IMAGES[os_name])
    s = s.replace("PYTHON_VERSION", python_version)
    fname = f"pytest-{os_name}-{python_version}.yml"
    ![echo @(s) > @(fname)]
