#!/usr/bin/env python3
"""Build and run Xonsh in a fresh, controlled environment using a container engine."""

import argparse
import os
import shutil
import subprocess
import sys


PROGRAM_DESCRIPTION = (
    "Build and run Xonsh in a fresh, controlled environment "
    "using docker or podman."
)

CPYTHON_DOCKERFILE = """\
from python:{python_version}
RUN pip install --upgrade pip && pip install {packages}
RUN mkdir /xonsh
WORKDIR /xonsh
ADD ./ ./
RUN python setup.py install
"""

PYPY_DOCKERFILE = """\
from pypy:{python_version}
RUN pypy3 -m ensurepip
RUN pip install --upgrade pip && pip install {packages}
RUN mkdir /xonsh
WORKDIR /xonsh
ADD ./ ./
RUN pypy3 setup.py install
"""


def parse_args():
    parser = argparse.ArgumentParser(description=PROGRAM_DESCRIPTION)
    parser.add_argument("env", nargs="*", default=[], metavar="ENV=value")
    parser.add_argument("--python", "-p", default="3.11", metavar="python_version")
    parser.add_argument("--pypy", default=None, metavar="pypy_version")
    parser.add_argument("--ptk", "-t", default="3.0.47", metavar="ptk_version")
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--command", "-c", default="xonsh", metavar="command")
    parser.add_argument("--pytest", action="store_true")
    parser.add_argument(
        "--engine",
        "-E",
        choices=["docker", "podman"],
        default="docker",
        help="container engine to use (default: docker)",
    )
    return parser.parse_args()


def render_dockerfile(args):
    template = PYPY_DOCKERFILE if args.pypy else CPYTHON_DOCKERFILE
    packages = [f"prompt-toolkit=={args.ptk}", "pygments"]
    if args.pytest:
        packages.append("pytest")
    return template.format(
        python_version=args.pypy or args.python,
        packages=" ".join(packages),
    )


def ensure_engine_available(engine):
    if shutil.which(engine) is None:
        sys.exit(
            f"error: container engine '{engine}' is not installed or not in PATH"
        )


def build_image(engine, dockerfile):
    try:
        with open("./Dockerfile", "w+") as f:
            f.write(dockerfile)
        subprocess.run([engine, "build", "-t", "xonsh", "."], check=True)
    finally:
        if os.path.exists("./Dockerfile"):
            os.remove("./Dockerfile")


def run_container(engine, env, keep, command):
    run_args = [engine, "run", "-ti"]
    for e in env:
        run_args += ["-e", e]
    if not keep:
        run_args.append("--rm")
    run_args += ["xonsh", command]
    subprocess.run(run_args, check=True)


def main():
    args = parse_args()

    ensure_engine_available(args.engine)

    print("Building and running Xonsh")
    print("Using container engine ", args.engine)
    print("Using python ", args.pypy or args.python)
    print("Using prompt-toolkit ", args.ptk)

    try:
        build_image(args.engine, render_dockerfile(args))
    except subprocess.CalledProcessError as exc:
        sys.exit(f"error: image build failed (exit code {exc.returncode})")

    if not args.build:
        try:
            run_container(args.engine, args.env, args.keep, args.command)
        except subprocess.CalledProcessError as exc:
            sys.exit(f"error: container exited with code {exc.returncode}")


if __name__ == "__main__":
    main()
