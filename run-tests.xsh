#!/usr/bin/env xonsh
import argparse
from typing import List


$RAISE_SUBPROC_ERROR = True


def _replace_args(args:List[str], num:int) -> List[str]:
    return [
         (arg % num) if "%d" in arg else arg
         for arg in args
    ]


def test(ns: argparse.Namespace):
    """Run pytest.

    Examples
    --------
    `xonsh run-tests.xsh -- --junitxml=junit/test-results.%%d.xml`
    """

    run_separately = [
        'tests/test_main.py',
        'tests/test_ptk_highlight.py',
    ]

    ignores = []
    for fname in run_separately:
        ignores.append('--ignore')
        ignores.append(fname)

    args = ns.args if "arg" in ns else []

    ![pytest @(_replace_args(args, 0)) @(ignores)]
    for index, fname in enumerate(run_separately):
        ![pytest @(_replace_args(args, index+1)) @(fname)]


def qa(ns: argparse.Namespace):
    """QA checks.
    """
    echo "---------- Running flake8 ----------"
    python -m flake8

    echo "---------- Running mypy ----------"
    mypy --version
    mypy xonsh

    echo "---------- Check Black formatter -----------"
    black --check xonsh xontrib


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers()

    test_parser = commands.add_parser('test', help=test.__doc__)
    test_parser.add_argument(
        'pytest_args',
        nargs='*',
        help="arbitrary arguments that gets passed to pytest's invocation."
             " Use %%d to parameterize and prevent overwrite "
    )
    test_parser.set_defaults(func=test)

    qa_parser = commands.add_parser('qa', help=qa.__doc__)
    qa_parser.set_defaults(func=test)

    args = parser.parse_args()
    args.func(args)
