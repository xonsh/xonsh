#!/usr/bin/env xonsh
"""Generates workflow files for each build matrix element. This is done
so that we can restart indivual workflow elements without having to restart
them all. Rerun this script to regenerate.
"""
from itertools import product
import os
import jinja2
from pathlib import Path

CURR_DIR = Path(__file__).absolute().parent
environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader(CURR_DIR),
    trim_blocks=True,
    lstrip_blocks=True,
)
tmpl = environment.get_template("pytest.tmpl")

OS_NAMES = ["linux", "macos", "windows"]
OS_IMAGES = {
    "linux": "ubuntu-latest",
    "macos": "macOS-latest",
    "windows": "windows-latest",
}
PY_MAIN_VERSION = "3.8"
PYTHON_VERSIONS = ["3.6", "3.7", PY_MAIN_VERSION, "3.9"]

ALLOWED_FAILURES = ["3.9"]


def write_to_file(
    tst: str, os_name: str, python_version: str, report_coverage=False, **kwargs
):
    fname = os.path.join(CURR_DIR, f"{tst}-{os_name}-{python_version}.yml")
    result = tmpl.render(
        OS_NAME=os_name,
        OS_IMAGE=OS_IMAGES[os_name],
        PYTHON_VERSION=python_version,
        NAME=tst,
        allow_failure=python_version in ALLOWED_FAILURES,
        report_coverage=report_coverage,
        **kwargs,
    )
    (CURR_DIR / fname).write_text(result)


# pytest workflows
for os_name, python_version in product(OS_NAMES, PYTHON_VERSIONS):
    report_coverage = python_version == PY_MAIN_VERSION and os_name == "linux"
    if report_coverage:
        test_cmd = "test --report-coverage -- --timeout=240"
    else:
        test_cmd = "test -- --timeout=240"

    write_to_file(
        "pytest",
        os_name,
        python_version,
        report_coverage=report_coverage,
        test_cmd=test_cmd,
    )

# qa workflow
write_to_file("qa", "linux", "3.8", test_cmd="qa")
